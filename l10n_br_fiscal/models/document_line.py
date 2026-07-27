# Copyright (C) 2013  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..tools import cfop_geography_warning


class DocumentLine(models.Model):
    """
    Represents a line item within a Brazilian fiscal document.

    This model defines the core structure of a fiscal document line,
    primarily linking it to its parent document (`l10n_br_fiscal.document`)
    and holding essential line-specific data like quantity and a
    descriptive name.

    The vast majority of detailed fiscal fields (e.g., product, NCM,
    CFOP, various tax bases and values) and their complex computation
    logic are inherited from `l10n_br_fiscal.document.line.mixin`.
    This delegation ensures code reusability and keeps this model
    focused on its direct relationships and core line properties.
    """

    _name = "l10n_br_fiscal.document.line"
    _inherit = "l10n_br_fiscal.document.line.mixin"
    _description = "Fiscal Document Line"

    document_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document",
        string="Document",
        ondelete="cascade",
    )

    name = fields.Char(
        compute="_compute_name",
        store=True,
        precompute=True,
        readonly=False,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        related="document_id.company_id",
        store=True,
        precompute=True,
        string="Company",
    )

    tax_framework = fields.Selection(
        related="company_id.tax_framework",
    )

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        compute="_compute_partner_id",
        store=True,
        precompute=True,
        readonly=False,
    )

    # Do not depend on `document_id.partner_id`, the inverse is taking care of that
    def _compute_partner_id(self):
        for line in self:
            line.partner_id = line.document_id.partner_id

    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="UOM",
        compute="_compute_uom_id",
        store=True,
        readonly=False,
        precompute=True,
    )

    price_unit = fields.Float(
        digits="Product Price",
        compute="_compute_price_unit_fiscal",
        store=True,
        precompute=True,
        readonly=False,
    )

    quantity = fields.Float(default=1.0)

    # Usado para tornar Somente Leitura os campos dos custos
    # de entrega quando a definição for por Total
    delivery_costs = fields.Selection(
        related="company_id.delivery_costs",
    )

    force_compute_delivery_costs_by_total = fields.Boolean(
        related="document_id.force_compute_delivery_costs_by_total"
    )

    edoc_purpose = fields.Selection(
        related="document_id.edoc_purpose",
    )

    additional_data = fields.Text()

    import_state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("matched", "Matched"),
            ("resolved", "Resolved"),
        ],
        copy=False,
        index=True,
        help="Review state of a line imported from a fiscal document file. "
        "Pending: no internal product resolved yet. Matched: an automatic "
        "suggestion needs confirmation. Resolved: the mapping was applied. "
        "Empty on lines that were not imported.",
    )

    import_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Import UoM",
        copy=False,
        help="Internal UoM equivalent to the supplier unit of the imported line.",
    )

    import_uom_factor = fields.Float(
        string="Import UoM Factor",
        default=1.0,
        copy=False,
        help="Conversion factor between the supplier unit and the internal "
        "UoM (e.g. 25 for a 25kg bag received in KG).",
    )

    import_supplierinfo_id = fields.Many2one(
        comodel_name="product.supplierinfo",
        string="Import Supplier Info",
        copy=False,
    )

    # Snapshot of the supplier values, like partner_cfop_id (mixin) for the CFOP.
    partner_uom_code = fields.Char(
        readonly=True,
        copy=False,
        help="Unit of measure as declared by the counterparty in the "
        "imported document.",
    )

    partner_quantity = fields.Float(
        digits="Product Unit of Measure",
        readonly=True,
        copy=False,
        help="Quantity as declared by the counterparty, in its own unit.",
    )

    partner_price_unit = fields.Float(
        digits="Product Price",
        readonly=True,
        copy=False,
        help="Unit price as declared by the counterparty, in its own unit.",
    )

    cfop_warning = fields.Char(
        compute="_compute_cfop_warning",
        string="CFOP Alert",
        help="Warns when the CFOP declared by the counterparty is "
        "inconsistent with the actual issuer/company geography. Useful to "
        "spot supplier mistakes before they pollute the SPED books.",
    )

    @api.depends("product_id")
    def _compute_name(self):
        for line in self:
            if line._is_imported() and line.name:
                line.name = line.name
                continue
            if line.product_id:
                line.name = line.product_id.display_name
            else:
                line.name = False

    @api.depends("product_id")
    def _compute_uom_id(self):
        for line in self:
            if line._is_imported() and line.uom_id:
                line.uom_id = line.uom_id
                continue
            if line.fiscal_operation_type == "in":
                line.uom_id = line.product_id.uom_po_id
            else:
                line.uom_id = line.product_id.uom_id

    @api.depends(
        "partner_cfop_id",
        "document_id.partner_id.state_id",
        "document_id.partner_id.country_id",
    )
    def _compute_cfop_warning(self):
        for line in self:
            line.cfop_warning = line._get_cfop_warning()

    def _get_cfop_warning(self):
        """Compare the declared CFOP scope with the real geography."""
        self.ensure_one()
        if self.document_id.fiscal_operation_type != "in":
            return False
        return cfop_geography_warning(
            self.partner_cfop_id.code,
            self.document_id.partner_id,
            self.company_id,
        )

    def action_resolve_line(self):
        for line in self:
            if not line.product_id:
                raise UserError(
                    _("Set the internal product before resolving the line %s.")
                    % (line.name or line.id)
                )
            line._apply_import_depara()

    def _apply_import_depara(
        self, product=None, uom=None, factor=None, fiscal_operation=None
    ):
        """Apply the reviewed de-para on a line imported from a fiscal file.

        Snapshots the supplier values (unit, quantity, unit price) once and
        converts the line to the internal unit from them: quantity times the
        factor, unit price divided by it, so the line total is preserved.
        """
        self.ensure_one()
        if not self._is_imported():
            raise UserError(
                _("The mapping can only be applied on imported document lines.")
            )
        product = product or self.product_id
        uom = uom or self.import_uom_id
        factor = factor or self.import_uom_factor or 1.0
        fiscal_operation = fiscal_operation or self.fiscal_operation_id

        if self.import_state != "resolved":
            # a resolved line holds converted values: snapshot only once
            self.write(
                {
                    "partner_uom_code": self.partner_uom_code
                    or self._get_partner_uom_code(),
                    "partner_quantity": self.quantity,
                    "partner_price_unit": self.price_unit,
                }
            )

        declared_quantity = self.partner_quantity or self.quantity
        declared_price_unit = self.partner_price_unit or self.price_unit
        vals = {
            "import_state": "resolved",
            "import_uom_factor": factor,
            "quantity": declared_quantity * factor,
            "price_unit": declared_price_unit / factor,
        }
        if product:
            vals["product_id"] = product.id
        if uom:
            vals["import_uom_id"] = uom.id
            vals["uom_id"] = uom.id
        if fiscal_operation:
            vals["fiscal_operation_id"] = fiscal_operation.id
        self.write(vals)
        if product:
            self._find_or_create_supplierinfo()
        return True

    # Supplier nomenclature hooks, implemented by each fiscal document type.
    def _get_partner_product_code(self):
        self.ensure_one()
        return False

    def _get_partner_product_name(self):
        self.ensure_one()
        return False

    def _get_partner_uom_code(self):
        """Unit code as declared by the counterparty (e.g. the uCom of an NFe)."""
        self.ensure_one()
        return False

    def _suggest_fiscal_operation_in(self):
        """Suggest the inbound operation from the inverse of the declared CFOP.

        The supplier declares an outbound CFOP (5xxx/6xxx/7xxx) and the
        operation lines of the company reference the inbound one (1xxx/2xxx/3xxx).
        """
        self.ensure_one()
        cfop_inverse = self.partner_cfop_id.cfop_inverse_id
        if not cfop_inverse:
            return self.env["l10n_br_fiscal.operation"]
        operation_lines = self.env["l10n_br_fiscal.operation.line"].search(
            [
                ("state", "=", "approved"),
                ("fiscal_operation_type", "=", "in"),
                "|",
                "|",
                ("cfop_internal_id", "=", cfop_inverse.id),
                ("cfop_external_id", "=", cfop_inverse.id),
                ("cfop_export_id", "=", cfop_inverse.id),
            ]
        )
        return operation_lines[:1].fiscal_operation_id

    def _get_supplierinfo_price(self):
        """Price of the supplier info in the product main UoM, from the
        converted unit price of the line (not from the supplier snapshot)."""
        self.ensure_one()
        if not self.price_unit:
            return False
        uom = self.import_uom_id or self.uom_id
        if uom:
            return uom._compute_price(self.price_unit, self.product_id.uom_id)
        return self.price_unit

    def _prepare_supplierinfo_vals(self):
        """Common supplier info values, extended by the document types."""
        self.ensure_one()
        vals = {
            "product_id": self.product_id.id,
            "product_name": self._get_partner_product_name() or self.name,
            "product_code": self._get_partner_product_code(),
        }
        price = self._get_supplierinfo_price()
        if price:
            vals["price"] = price
        return vals

    def _find_or_create_supplierinfo(self):
        for line in self:
            partner = line.document_id.partner_id
            if not line.product_id or not partner:
                continue
            supplierinfo_model = line.env["product.supplierinfo"].with_company(
                line.company_id
            )
            supplierinfo = line.import_supplierinfo_id
            product = line.product_id
            product_code = line._get_partner_product_code()
            if not supplierinfo:
                domain = [
                    ("partner_id", "=", partner.id),
                    ("product_code", "=", product_code),
                ]
                if product_code:
                    # a seller entered by hand sits on the template
                    domain += [
                        "|",
                        ("product_id", "=", product.id),
                        ("product_tmpl_id", "=", product.product_tmpl_id.id),
                    ]
                else:
                    # without the supplier code only the sellers created here
                    # (on the variant) are adopted, never a hand made one
                    domain.append(("product_id", "=", product.id))
                supplierinfo = supplierinfo_model.search(domain, limit=1)
            if supplierinfo:
                supplierinfo.write(line._prepare_supplierinfo_vals())
                line.import_supplierinfo_id = supplierinfo
            else:
                vals = line._prepare_supplierinfo_vals()
                vals["partner_id"] = partner.id
                line.import_supplierinfo_id = supplierinfo_model.create(vals)
                line.product_id.product_tmpl_id.seller_ids = [
                    fields.Command.link(line.import_supplierinfo_id.id)
                ]

    def __document_comment_vals(self):
        self.ensure_one()
        return {
            "user": self.env.user,
            "ctx": self._context,
            "doc": self.document_id if hasattr(self, "document_id") else None,
            "item": self,
        }

    def _document_comment(self):
        for line in self:
            line.additional_data = line.comment_ids.compute_message(
                line.__document_comment_vals(), line.manual_additional_data
            )

    @api.model
    def _add_imported_ibscbs_vals(self, ibscbs, vals):
        """Merge into ``vals`` the IBS/CBS values of an imported IBSCBS
        binding node (NFe and CTe share the same DFe schema for it).

        Returns the list of matched fiscal tax ids so each caller can
        link them into ``fiscal_tax_ids`` with its own convention (the
        NFe import framework expects raw ids, the CTe one expects
        Command tuples).
        """
        tax_ids = []
        if not (ibscbs and ibscbs.gIBSCBS):
            return tax_ids

        gibscbs = ibscbs.gIBSCBS
        base = float(gibscbs.vBC) if gibscbs.vBC else 0.0

        ibs_percent = ibs_value = 0.0
        if gibscbs.gIBSUF:
            ibs_percent = float(gibscbs.gIBSUF.pIBSUF) if gibscbs.gIBSUF.pIBSUF else 0.0
            ibs_value = float(gibscbs.gIBSUF.vIBSUF) if gibscbs.gIBSUF.vIBSUF else 0.0
        cbs_percent = cbs_value = 0.0
        if gibscbs.gCBS:
            cbs_percent = float(gibscbs.gCBS.pCBS) if gibscbs.gCBS.pCBS else 0.0
            cbs_value = float(gibscbs.gCBS.vCBS) if gibscbs.gCBS.vCBS else 0.0

        cst_code = ibscbs.CST if ibscbs.CST else "000"
        cst_ibs = self.env.ref(
            f"l10n_br_fiscal.cst_ibs_{cst_code}", raise_if_not_found=False
        )
        if cst_ibs:
            vals["ibs_cst_id"] = cst_ibs.id
        cst_cbs = self.env.ref(
            f"l10n_br_fiscal.cst_cbs_{cst_code}", raise_if_not_found=False
        )
        if cst_cbs:
            vals["cbs_cst_id"] = cst_cbs.id

        if ibscbs.cClassTrib:
            tax_classification = self.env["l10n_br_fiscal.tax.classification"].search(
                [("code", "=", ibscbs.cClassTrib)], limit=1
            )
            if tax_classification:
                vals["tax_classification_id"] = tax_classification.id

        vals.update(
            ibs_base=base,
            ibs_percent=ibs_percent,
            ibs_value=ibs_value,
            cbs_base=base,
            cbs_percent=cbs_percent,
            cbs_value=cbs_value,
        )

        ibs_tax = self.env["l10n_br_fiscal.tax"].search(
            [
                ("tax_group_id", "=", self.env.ref("l10n_br_fiscal.tax_group_ibs").id),
                ("percent_amount", "=", ibs_percent),
            ],
            limit=1,
        )
        if ibs_tax:
            vals["ibs_tax_id"] = ibs_tax.id
            tax_ids.append(ibs_tax.id)
        cbs_tax = self.env["l10n_br_fiscal.tax"].search(
            [
                ("tax_group_id", "=", self.env.ref("l10n_br_fiscal.tax_group_cbs").id),
                ("percent_amount", "=", cbs_percent),
            ],
            limit=1,
        )
        if cbs_tax:
            vals["cbs_tax_id"] = cbs_tax.id
            tax_ids.append(cbs_tax.id)
        return tax_ids
