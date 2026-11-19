# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

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

    @api.model
    def _build_attr(self, node, fields, vals, path, attr):
        result = super()._build_attr(node, fields, vals, path, attr)
        if self.env.context.get(NO_CREATE_CONTEXT_KEY):
            key = f"nfe40_{attr[0]}"
            if key in REGISTRY_MIRROR_KEYS:
                vals.pop(key, None)
            declared = getattr(node, attr[0], None)
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
