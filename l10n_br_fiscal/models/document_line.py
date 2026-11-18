# Copyright (C) 2013  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..constants.fiscal import (
    FISCAL_IN,
    PIS_COFINS_CST_ENTRY_WITHOUT_CREDIT,
    PRODUCT_DESTINATION_CREDIT,
    PROFIT_CALCULATION_REAL,
    TAX_DOMAIN_COFINS,
    TAX_DOMAIN_IPI,
    TAX_DOMAIN_PIS,
    TAX_FRAMEWORK_SIMPLES_ALL,
)
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

    # Review of lines imported from a fiscal file (draft-first import flow).
    # The document is materialized faithfully from the file and each line is
    # then reviewed: the de-para (supplier nomenclature -> company fiscal
    # settings) is applied on the persisted line, keeping the supplier data
    # as a snapshot for bookkeeping and audit.
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
        "suggestion needs confirmation. Resolved: the de-para was applied. "
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

    # Snapshot of the supplier values, taken when the de-para converts the
    # line to the internal nomenclature. partner_cfop_id (mixin) is the same
    # pattern for the CFOP.
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

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == "form":
            arch = self._add_entry_cst_fields(arch)
        return arch, view

    @api.model
    def _add_entry_cst_fields(self, arch):
        """The CST of the entry of the company, read only, right after the CST
        of the file on the tabs of the taxes.

        They are fields of this model only (an imported entry), while the form
        of the fiscal taxes is a template shared by every model that carries the
        fiscal mixin (purchase, sale, stock, invoice lines), where they do not
        exist: they are added here, not in the shared template.
        """
        for tax in ("ipi", "pis", "cofins"):
            anchors = arch.xpath(
                f".//page[@name='{tax}']//field[@name='{tax}_cst_code']"
            )
            name = f"entry_{tax}_cst_id"
            if not anchors or arch.xpath(f".//field[@name='{name}']"):
                continue
            field = etree.Element(
                "field",
                name=name,
                readonly="1",
                attrs=f"{{'invisible': [('{name}', '=', False)]}}",
                options="{'no_create': True, 'no_open': True}",
            )
            anchors[0].addnext(field)
        return arch

    # What the supplier declared (ipi_cst_id, pis_cst_id, cofins_cst_id: the CSTs
    # of the file, never touched) and what the company books for the entry are
    # kept apart, both stored. The books read the entry CST when it exists.
    entry_ipi_cst_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.cst",
        string="IPI CST of the Entry (company)",
        domain="[('tax_domain', '=', 'ipi'), ('cst_type', 'in', ('in', 'all'))]",
        compute="_compute_entry_cst_ids",
        store=True,
        readonly=False,
        copy=False,
        help="IPI CST the company books for this entry, from the fiscal operation "
        "of the entry. The CST in the imported file is the one of the supplier "
        "(an outgoing operation) and stays as it came.",
    )

    entry_pis_cst_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.cst",
        string="PIS CST of the Entry (company)",
        domain="[('tax_domain', '=', 'pis'), ('cst_type', 'in', ('in', 'all'))]",
        compute="_compute_entry_cst_ids",
        store=True,
        readonly=False,
        copy=False,
        help="PIS CST the company books for this entry: the credit CST of the "
        "operation in the non-cumulative regime, 70 (acquisition without credit "
        "right) in the cumulative one.",
    )

    entry_cofins_cst_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.cst",
        string="COFINS CST of the Entry (company)",
        domain="[('tax_domain', '=', 'cofins'), ('cst_type', 'in', ('in', 'all'))]",
        compute="_compute_entry_cst_ids",
        store=True,
        readonly=False,
        copy=False,
        help="COFINS CST the company books for this entry: the credit CST of the "
        "operation in the non-cumulative regime, 70 (acquisition without credit "
        "right) in the cumulative one.",
    )

    @api.depends(
        "fiscal_operation_line_id",
        "product_id",
        "partner_id",
        "ncm_id",
        "company_id.profit_calculation",
        "product_destination",
        "document_id.imported_document",
    )
    def _compute_entry_cst_ids(self):
        """The entry CSTs only exist for an entry imported from a fiscal file:
        there the taxes stay the ones of the file and the mapping of the entry
        operation was discarded. Any other line does not use them: its own
        CSTs are the ones of the operation.

        Cost of the first ``-u``: the compute runs once for every existing line
        and returns at the first check unless the line is an imported entry,
        which is the only one that maps the operation again.
        """
        for line in self:
            ipi = pis = cofins = self.env["l10n_br_fiscal.cst"]
            if (
                line._is_imported()
                and line.fiscal_operation_type == FISCAL_IN
                and line.fiscal_operation_line_id
            ):
                taxes = line._map_fiscal_taxes_of_line()["taxes"]
                ipi = taxes.get(TAX_DOMAIN_IPI, ipi).cst_in_id
                pis = line._get_entry_piscofins_cst(
                    TAX_DOMAIN_PIS, taxes.get(TAX_DOMAIN_PIS)
                )
                cofins = line._get_entry_piscofins_cst(
                    TAX_DOMAIN_COFINS, taxes.get(TAX_DOMAIN_COFINS)
                )
            line.entry_ipi_cst_id = ipi
            line.entry_pis_cst_id = pis
            line.entry_cofins_cst_id = cofins

    def _get_entry_piscofins_cst(self, tax_domain, tax):
        """PIS/COFINS CST of an entry by the regime of the company.

        Non-cumulative (real profit): the credit CST of the mapped tax, only for
        a destination that gives the credit (resale and industrialization, the
        same ones the ledger credits: ``_get_stock_cost_tax_map``); use and
        consumption and the fixed asset are 70, acquisition without credit
        right.
        Cumulative (presumed or arbitrated profit): 70 as well, whatever the
        operation maps. Simples Nacional does not take the credit either, but it
        has no PIS/COFINS book: it keeps the mapped CST.
        """
        self.ensure_one()
        company = self.company_id
        if company.tax_framework not in TAX_FRAMEWORK_SIMPLES_ALL and (
            company.profit_calculation != PROFIT_CALCULATION_REAL
            or (
                self.product_destination
                and self.product_destination not in PRODUCT_DESTINATION_CREDIT
            )
        ):
            return self.env.ref(f"l10n_br_fiscal.cst_{tax_domain}_70")
        return tax.cst_in_id if tax else self.env["l10n_br_fiscal.cst"]

    def _entry_piscofins_without_credit(self, tax_domain):
        """True when the entry books PIS or COFINS without credit right (CST 70
        to 75): the book then carries no base, rate or value for the tax."""
        self.ensure_one()
        cst = self[f"entry_{tax_domain}_cst_id"]
        return cst.code in PIS_COFINS_CST_ENTRY_WITHOUT_CREDIT

    @api.depends("product_id")
    def _compute_name(self):
        for line in self:
            if line._is_imported() and line.name:
                # Preserve the description imported from the fiscal file.
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
                # Preserve the unit imported from the fiscal file; the
                # internal unit is applied via _apply_import_depara().
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
        """Compare the declared CFOP scope with the real issuer/company
        geography (see ``tools.cfop_geography_warning``)."""
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
        self, product=None, uom=None, factor=None, fiscal_operation=None, confirm=True
    ):
        """Apply the reviewed de-para on a line imported from a fiscal file.

        This is the single write path of the de-para: it snapshots the
        supplier values (unit, quantity, unit price), converts the line to
        the internal nomenclature preserving the line total (quantity is
        multiplied by the factor, the unit price divided by it), applies the
        fiscal operation of the line and persists the supplier info
        learning. The original file stays untouched as an attachment.

        With ``confirm=False`` the product is only a suggestion (it was found
        by the import through the code, the barcode or the name): it is set on
        the line, which stays ``matched``, and nothing is learned until a
        person confirms it (``action_resolve_line``).
        """
        self.ensure_one()
        if not self._is_imported():
            raise UserError(
                _("The de-para can only be applied on imported document lines.")
            )
        product = product or self.product_id
        uom = uom or self.import_uom_id
        factor = factor or self.import_uom_factor or 1.0
        fiscal_operation = fiscal_operation or self.fiscal_operation_id

        if not self.partner_uom_code:
            self.write(
                {
                    "partner_uom_code": self.uom_id.code or self.uom_id.name,
                    "partner_quantity": self.quantity,
                    "partner_price_unit": self.price_unit,
                }
            )

        vals = {
            "import_state": "resolved" if confirm else "matched",
            "import_uom_factor": factor,
        }
        if product:
            vals["product_id"] = product.id
        if uom:
            vals["import_uom_id"] = uom.id
            vals["uom_id"] = uom.id
            if factor != 1.0:
                vals["quantity"] = self.partner_quantity * factor
                vals["price_unit"] = self.partner_price_unit / factor
        if fiscal_operation:
            vals["fiscal_operation_id"] = fiscal_operation.id
        self.write(vals)
        if product and confirm:
            self._find_or_create_supplierinfo()
        return True

    # Supplier nomenclature hooks: implemented by each fiscal document type
    # (e.g. l10n_br_nfe reads nfe40_cProd / nfe40_cEANTrib / nfe40_xProd).
    def _get_partner_product_code(self):
        self.ensure_one()
        return False

    def _get_partner_product_barcode(self):
        self.ensure_one()
        return False

    def _get_partner_product_name(self):
        self.ensure_one()
        return False

    def _suggest_product(self):
        """Suggest an internal product for an imported line.

        Priority: the supplier info de-para already learned for this partner
        and supplier code, then the internal reference, then the barcode.
        """
        self.ensure_one()
        product_model = self.env["product.product"]
        code = self._get_partner_product_code()
        partner = self.document_id.partner_id
        if code and partner:
            supplierinfo = self.env["product.supplierinfo"].search(
                [
                    ("partner_id", "=", partner.id),
                    ("product_code", "=", code),
                ],
                limit=1,
            )
            product = (
                supplierinfo.product_id
                or supplierinfo.product_tmpl_id.product_variant_id
            )
            if product:
                return product
        if code:
            product = product_model.search([("default_code", "=", code)], limit=1)
            if product:
                return product
        barcode = self._get_partner_product_barcode()
        if barcode and barcode != "SEM GTIN":
            product = product_model.search([("barcode", "=", barcode)], limit=1)
            if product:
                return product
        return product_model

    def _suggest_fiscal_operation_in(self):
        """Suggest the inbound fiscal operation of the line from the CFOP
        declared by the counterparty, through its inverse CFOP.

        The supplier declares an outbound CFOP (5xxx/6xxx/7xxx); the inverse
        CFOP (1xxx/2xxx/3xxx) is the company side of the same operation, and
        the approved operation lines referencing it tell which fiscal
        operations the company configured for that kind of entry.
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
        """Price of the supplier info expressed in the product main UoM."""
        self.ensure_one()
        price = self.partner_price_unit or self.price_unit
        if self.import_uom_id:
            return self.import_uom_id._compute_price(price, self.product_id.uom_id)
        return self.product_id.lst_price

    def _prepare_supplierinfo_vals(self):
        """Common supplier info values.

        Overriden by specialized document types (e.g. NFe) to add the
        partner UoM de-para values.
        """
        self.ensure_one()
        return {
            "product_id": self.product_id.id,
            "product_name": self._get_partner_product_name() or self.name,
            "product_code": self._get_partner_product_code(),
            "price": self._get_supplierinfo_price(),
        }

    def _find_or_create_supplierinfo(self):
        for line in self:
            if not line.product_id or not line.document_id.partner_id:
                continue
            # The de-para memory is a by-product of the import: the fiscal
            # profile that runs it has no purchase (product.supplierinfo)
            # access rights.
            if not line.import_supplierinfo_id:
                vals = line._prepare_supplierinfo_vals()
                vals["partner_id"] = line.document_id.partner_id.id
                line.import_supplierinfo_id = (
                    line.env["product.supplierinfo"].sudo().create(vals)
                )
                line.product_id.product_tmpl_id.sudo().seller_ids = [
                    fields.Command.link(line.import_supplierinfo_id.id)
                ]
            else:
                line.import_supplierinfo_id.sudo().write(
                    line._prepare_supplierinfo_vals()
                )

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
