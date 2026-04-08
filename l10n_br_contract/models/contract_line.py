# Copyright 2020 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ContractLine(models.Model):
    _name = "contract.line"
    _inherit = [_name, "l10n_br_fiscal.document.line.mixin"]

    document_id = fields.Many2one(
        comodel_name="contract.contract",
        related="contract_id",
        string="Fiscal Document",
        store=True,
        readonly=True,
    )

    # Keep fiscal tax fields precompute-compatible on contract.line.
    # These overrides preserve original compute/inverse/store behavior
    # from contract.template.line and only add precompute.
    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        compute="_compute_uom_id",
        store=True,
        readonly=False,
        precompute=True,
        string="Unit of Measure",
        domain="[('category_id', '=', product_uom_category_id)]",
    )
    automatic_price = fields.Boolean(
        string="Auto-price?",
        compute="_compute_automatic_price",
        store=True,
        readonly=False,
        precompute=True,
        help=(
            "If checked, the price will be taken from the pricelist. "
            "Otherwise, it must be set manually."
        ),
    )
    price_unit = fields.Float(
        string="Unit Price",
        compute="_compute_price_unit",
        inverse="_inverse_price_unit",
        store=True,
        precompute=True,
    )

    company_id = fields.Many2one(
        related="contract_id.company_id",
    )
    country_id = fields.Many2one(related="company_id.country_id", store=True)

    fiscal_tax_ids = fields.Many2many(
        comodel_name="l10n_br_fiscal.tax",
        relation="fiscal_contract_line_tax_rel",
        column1="document_id",
        column2="fiscal_tax_id",
        string="Fiscal Taxes",
    )

    tax_framework = fields.Selection(
        related="contract_id.company_id.tax_framework",
        string="Tax Framework",
    )

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        related="contract_id.partner_id",
        string="Partner",
    )

    ind_final = fields.Selection(related="contract_id.ind_final", store=True)

    comment_ids = fields.Many2many(
        comodel_name="l10n_br_fiscal.comment",
        relation="contract_line_comment_rel",
        column1="contract_line_id",
        column2="comment_id",
        string="Comments",
    )

    simple_without_icms_value = fields.Monetary(
        string="National Simple Taxes without ICMS",
        compute="_compute_tax_fields",
        store=True,
        readonly=False,
    )

    def _is_imported(self):
        return False

    def _prepare_invoice_line(self):
        self.ensure_one()

        contract = self.contract_id

        if contract.contract_recalculate_taxes_before_invoice:
            self._compute_fiscal_tax_ids()

        invoice_line_vals = super()._prepare_invoice_line()

        # Por algum motivo com a localização o campo company_currency_id
        # nao vem em invoice_line_val e isto impacta com o modulo contract
        invoice_line_vals.update(
            {"company_currency_id": contract.company_id.currency_id.id}
        )

        self._onchange_fiscal_taxes()
        quantity = invoice_line_vals.get("quantity")

        tax_ids = self.fiscal_tax_ids.account_taxes(user_type=contract.contract_type)
        if (
            contract.fiscal_operation_id
            and contract.fiscal_operation_id.deductible_taxes
        ):
            tax_ids |= self.fiscal_tax_ids.account_taxes(
                user_type=contract.contract_type
            )

        if invoice_line_vals:
            invoice_line_vals.update(self._prepare_br_fiscal_dict())
            invoice_line_vals["quantity"] = quantity
            invoice_line_vals["tax_ids"] = tax_ids.ids
        return invoice_line_vals
