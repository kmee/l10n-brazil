# Copyright 2022 KMEE (Renan Hiroki Bastos <renan.hiroki@kmee.com.br>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models

from odoo.addons.spec_driven_model.models import spec_models


class DocumentPayment(models.Model):
    _name = "l10n_br_nfe.document.payment"
    _description = "Dados da Cobrança"

    payment_line_ids = fields.One2many(
        comodel_name="l10n_br_nfe.document.payment.line",
        inverse_name="payment_id",
        string="Duplicatas",
        required=False,
    )

    fatura_id = fields.Many2one(
        comodel_name="l10n_br_nfe.document.fatura",
        string="Fatura",
    )


class NFeCobr(spec_models.StackedModel):
    _name = "l10n_br_nfe.document.payment"
    _inherit = ["l10n_br_nfe.document.payment", "nfe.40.cobr"]
    _stacked = "nfe.40.cobr"
    _field_prefix = "nfe40_"
    _schema_name = "nfe"
    _schema_version = "4.0.0"
    _odoo_module = "l10n_br_nfe"
    _spec_module = "odoo.addons.l10n_br_nfe_spec.models.v4_00.leiauteNFe"
    _spec_tab_name = "NFe"
    _stacking_points = {}
    # all m2o below this level will be stacked even if not required:
    _force_stack_paths = ()

    nfe40_dup = fields.One2many(
        comodel_name="l10n_br_nfe.document.payment.line",
        inverse_name="payment_id",
        string="Duplicatas",
        required=False,
    )

    nfe40_fat = fields.Many2one(related="fatura_id")


class DocumentFatura(models.Model):
    _name = "l10n_br_nfe.document.fatura"
    _description = "Dados da Fatura"

    payment_number = fields.Char(
        string="Número da Fatura",
    )

    amount_original = fields.Monetary(
        string="Valor Original", currency_field="currency_id"
    )

    amount_discount = fields.Monetary(
        string="Valor do Disconto", currency_field="currency_id"
    )

    amount_liquid = fields.Monetary(
        string="Valor Líquido", currency_field="currency_id"
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        readonly=True,
        default=lambda self: self.env.user.company_id.currency_id,
        track_visibility="always",
    )


class NFeFat(spec_models.StackedModel):
    _name = "l10n_br_nfe.document.fatura"
    _inherit = ["l10n_br_nfe.document.fatura", "nfe.40.fat"]
    _stacked = "nfe.40.fat"
    _field_prefix = "nfe40_"
    _schema_name = "nfe"
    _schema_version = "4.0.0"
    _odoo_module = "l10n_br_nfe"
    _spec_module = "odoo.addons.l10n_br_nfe_spec.models.v4_00.leiauteNFe"
    _spec_tab_name = "NFe"
    _stacking_points = {}
    # all m2o below this level will be stacked even if not required:
    _force_stack_paths = ()

    nfe40_nFat = fields.Char(related="payment_number")

    nfe40_vOrig = fields.Monetary(related="amount_original")

    nfe40_vDesc = fields.Monetary(related="amount_discount")

    nfe40_vLiq = fields.Monetary(related="amount_liquid")


class DocumentPaymentLine(models.Model):
    _name = "l10n_br_nfe.document.payment.line"
    _description = "Duplicatas"

    line_number = fields.Char(
        string="Número da Duplicata",
    )

    date_due = fields.Date(
        string="Data de Vencimento",
    )

    amount_total = fields.Monetary(string="Valor", currency_field="currency_id")

    payment_id = fields.Many2one(
        comodel_name="l10n_br_nfe.document.payment",
        string="Cobrança",
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        readonly=True,
        default=lambda self: self.env.user.company_id.currency_id,
        track_visibility="always",
    )

    def _get_company_currency(self):
        if self.document_id.company_id:
            self.currency_id = self.sudo().document_id.company_id.currency_id
        else:
            self.currency_id = self.env.user.company_id.currency_id


class NFeDupLine(spec_models.StackedModel):
    _name = "l10n_br_nfe.document.payment.line"
    _inherit = ["l10n_br_nfe.document.payment.line", "nfe.40.dup"]
    _stacked = "nfe.40.dup"
    _field_prefix = "nfe40_"
    _schema_name = "nfe"
    _schema_version = "4.0.0"
    _odoo_module = "l10n_br_nfe"
    _spec_module = "odoo.addons.l10n_br_nfe_spec.models.v4_00.leiauteNFe"
    _spec_tab_name = "NFe"
    _stacking_points = {}
    # all m2o below this level will be stacked even if not required:
    _force_stack_paths = ()

    nfe40_nDup = fields.Char(
        related="line_number",
    )

    nfe40_dVenc = fields.Date(
        related="date_due",
    )

    nfe40_vDup = fields.Monetary(
        related="amount_total",
    )
