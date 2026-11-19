# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.tools import float_compare

from .product_product import NO_CREATE_CONTEXT_KEY

# Char fields that mirror a registry record (NCM, CEST...): writing them when
# the record does not exist makes the ORM create an empty one.
REGISTRY_MIRROR_KEYS = (
    "nfe40_NCM",
    "nfe40_CEST",
    "nfe40_EXTIPI",
    "nfe40_CFOP",
    "nfe40_uCom",
    "nfe40_uTrib",
)


class DocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    import_ncm_code = fields.Char(
        string="NCM Declared",
        copy=False,
        readonly=True,
        help="NCM as declared in the imported file, kept as it came.",
    )

    import_price_gross = fields.Monetary(
        string="Import Gross Total",
        currency_field="currency_id",
        copy=False,
        help="Total value of the item as the supplier file declared it (vProd). "
        "The unit price has the precision of the price, and the de-para with a "
        "unit factor divides it, so quantity times price may not give back the "
        "cents of the file: the total of the line follows this value. Cleared "
        "when a person edits the quantity or the price.",
    )

    @api.model
    def _build_attr(self, node, fields, vals, path, attr):
        result = super()._build_attr(node, fields, vals, path, attr)
        if self.env.context.get(NO_CREATE_CONTEXT_KEY):
            key = f"nfe40_{attr[0]}"
            if key in REGISTRY_MIRROR_KEYS:
                vals.pop(key, None)
            declared = getattr(node, attr[0], None)
            if key == "nfe40_vProd" and declared is not None:
                vals["import_price_gross"] = float(declared)
            if key == "nfe40_NCM" and declared:
                vals["import_ncm_code"] = str(declared)
            if declared and key in ("nfe40_uCom", "nfe40_uTrib"):
                # no unit by omission: it stays empty when nothing matches
                uom = self.env["uom.uom"]._match_by_fiscal_code(str(declared))
                if key == "nfe40_uCom":
                    vals["partner_uom_code"] = str(declared)
                    vals["uom_id"] = uom.id or False
                else:
                    vals["uot_id"] = uom.id or False
        return result

    def _get_partner_product_code(self):
        return self.nfe40_cProd or super()._get_partner_product_code()

    def _get_partner_product_name(self):
        return self.nfe40_xProd or super()._get_partner_product_name()

    def _prepare_supplierinfo_vals(self):
        vals = super()._prepare_supplierinfo_vals()
        declared = self.env["uom.uom"]._match_by_fiscal_code(self.partner_uom_code)
        if declared:
            # the factor only holds for the unit it was learned with
            vals.update(
                {
                    "partner_uom_id": declared.id,
                    "partner_uom_factor": self.import_uom_factor or 1.0,
                }
            )
        return vals

    def _find_or_create_supplierinfo(self):
        # the de-para memory is a by-product of the review: the fiscal user has
        # no purchase rights, and the author of the line stays the same
        return super(DocumentLine, self.sudo())._find_or_create_supplierinfo()

    def _dfe_unit_unconfirmed(self):
        """The unit declared by the supplier was neither matched nor chosen."""
        self.ensure_one()
        if not self.partner_uom_code or self.import_uom_id:
            return False
        declared = self.env["uom.uom"]._match_by_fiscal_code(self.partner_uom_code)
        return not self.uom_id or declared != self.uom_id

    @api.depends("import_price_gross")
    def _compute_fiscal_amounts(self):
        result = super()._compute_fiscal_amounts()
        for line in self.filtered("import_price_gross"):
            delta = line.import_price_gross - line.price_gross
            if not delta:
                continue
            for name in (
                "price_gross",
                "amount_fiscal",
                "fiscal_amount_untaxed",
                "fiscal_amount_total",
                "amount_taxed",
            ):
                line[name] += delta
            for name in ("financial_total", "financial_total_gross"):
                if line[name]:
                    line[name] += delta
        return result

    def write(self, vals):
        if (
            self.env.context.get("dfe_import_apply")
            or "import_price_gross" in vals
            or not {"quantity", "price_unit"} & vals.keys()
        ):
            return super().write(vals)
        # a quantity or a price edited by a person gives the total back to the
        # calculation (the same values written back change nothing)
        edited = self.filtered(
            lambda line: line.import_price_gross
            and any(
                name in vals
                and float_compare(vals[name], line[name], precision_digits=8)
                for name in ("quantity", "price_unit")
            )
        )
        if edited:
            super(DocumentLine, edited).write(dict(vals, import_price_gross=0.0))
            return super(DocumentLine, self - edited).write(vals)
        return super().write(vals)

    def _apply_import_depara(self, *args, **kwargs):
        return super(
            DocumentLine, self.with_context(dfe_import_apply=True)
        )._apply_import_depara(*args, **kwargs)
