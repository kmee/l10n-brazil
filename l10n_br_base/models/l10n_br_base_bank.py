#    Copyright (C) 2016 MultidadosTI (http://www.multidadosti.com.br)
#    @author Michell Stuttgart <michellstut@gmail.com>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models


class L10nBrBaseBank(models.Model):
    """Brazilian banks (BCB table with COMPE code and ISPB).

    Odoo 20 removed ``res.bank``; bank accounts point here by ``l10n_br_bank_id``.
    """

    _name = "l10n_br_base.bank"
    _description = "Brazilian Bank"
    _order = "code_bc, name"
    _rec_names_search = ("name", "short_name", "code_bc", "ispb_number")

    name = fields.Char(required=True)

    short_name = fields.Char()

    code_bc = fields.Char(
        string="Brazilian Bank Code",
        size=3,
        help="Brazilian Bank Code ex.: 001 is the code of Banco do Brasil",
    )

    ispb_number = fields.Char(
        string="ISPB Number",
        size=8,
    )

    compe_member = fields.Boolean(
        string="COMPE Member",
        default=False,
    )

    bic = fields.Char(
        string="BIC/SWIFT",
        help="Bank Identifier Code of the institution.",
    )

    active = fields.Boolean(default=True)

    @api.depends("code_bc", "name")
    def _compute_display_name(self):
        for bank in self:
            bank.display_name = (
                f"{bank.code_bc} - {bank.name}" if bank.code_bc else bank.name
            )
