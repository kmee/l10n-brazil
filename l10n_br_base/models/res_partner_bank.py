# Copyright (C) 2009 Gabriel C. Stabel
# Copyright (C) 2009 Renato Lima (Akretion)
# Copyright (C) 2012 Raphaël Valyi (Akretion)
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models
from odoo.exceptions import UserError

BANK_ACCOUNT_TYPE = [
    ("01", "Conta corrente individual"),
    ("02", "Conta poupança individual"),
    ("03", "Conta depósito judicial/Depósito em consignação individual"),
    ("11", "Conta corrente conjunta"),
    ("12", "Conta poupança conjunta"),
    ("13", "Conta depósito judicial/Depósito em consignação conjunta"),
]

TRANSACTIONAL_ACCOUNT_TYPE = [
    ("checking", "Checking Account (Conta Corrente)"),
    ("saving", "Saving Account (Conta Poupança)"),
    ("payment", "Prepaid Payment Account (Conta Pagamento)"),
]


class ResPartnerBank(models.Model):
    """Adiciona campos necessários para o cadastramentos de contas
    bancárias no Brasil."""

    _inherit = "res.partner.bank"

    bank_account_type = fields.Selection(
        selection=BANK_ACCOUNT_TYPE,
        string="Brazilian Bank Account Type",
        default="01",
    )

    transactional_acc_type = fields.Selection(
        selection=TRANSACTIONAL_ACCOUNT_TYPE,
        string="Account Type",
        help="Type of transactional account, classification used in "
        "the Brazilian instant payment system (PIX)",
    )

    partner_pix_ids = fields.One2many(
        comodel_name="res.partner.pix",
        inverse_name="partner_bank_id",
        string="Pix Keys",
    )

    l10n_br_bank_id = fields.Many2one(
        comodel_name="l10n_br_base.bank",
        string="Brazilian Bank",
        help="Bank from the Brazilian Central Bank table (COMPE code and ISPB).",
    )

    bank_name = fields.Char(
        compute="_compute_l10n_br_bank_data",
        store=True,
        readonly=False,
    )

    bank_bic = fields.Char(
        compute="_compute_l10n_br_bank_data",
        store=True,
        readonly=False,
    )

    account_number = fields.Char(
        size=64,
        required=False,
    )

    acc_number_dig = fields.Char(
        string="Account Digit",
        size=8,
    )

    bra_number = fields.Char(
        string="Bank Branch",
        size=8,
    )

    bra_number_dig = fields.Char(
        string="Bank Branch Digit",
        size=8,
    )

    bra_bank_bic = fields.Char(
        string="BIC/Swift Final Code.",
        size=3,
        help="Last part of BIC/Swift Code.",
    )

    company_country_id = fields.Many2one(
        comodel_name="res.country",
        string="Company Country",
        related="company_id.country_id",
    )

    @api.depends("l10n_br_bank_id")
    def _compute_l10n_br_bank_data(self):
        for account in self:
            bank = account.l10n_br_bank_id
            account.bank_name = bank.name or account.bank_name
            account.bank_bic = bank.bic or account.bank_bic

    @api.constrains("bra_number")
    def _check_bra_number(self):
        for bank in self:
            if (
                bank.l10n_br_bank_id.code_bc
                and bank.bra_number
                and len(bank.bra_number) > 4
            ):
                raise UserError(self.env._("Bank branch code must be four characters."))

    @api.constrains(
        "transactional_acc_type",
        "l10n_br_bank_id",
        "account_number",
        "bra_number",
        "acc_number_dig",
    )
    def _check_transc_acc_type(self):
        for rec in self:
            if rec.transactional_acc_type and (
                not rec.l10n_br_bank_id.code_bc or not rec.account_number
            ):
                raise UserError(
                    self.env._(
                        "a transactional account must contain the bank "
                        "information (code_bc) and the account number"
                    )
                )
            if rec.transactional_acc_type in ["checking", "saving"] and (
                not rec.bra_number or not rec.acc_number_dig
            ):
                raise UserError(
                    self.env._(
                        "A Checking Account or Saving Account transactional account"
                        " must contain the branch number and the account"
                        " verification digit."
                    )
                )
