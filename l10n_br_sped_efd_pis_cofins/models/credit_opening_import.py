# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

import base64
from datetime import date, datetime, timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

# position of the fields in the registers 1100 and 1500 (descriptor of the PVA),
# counting the register name as 0
PER_APU_CRED = 2
ORIG_CRED = 3
CNPJ_SUC = 4
COD_CRED = 5
VL_TOT_CRED_APU = 8
SLD_CRED_FIM = 18

REGISTER_TAX = {"1100": "pis", "1500": "cofins"}


def _number(text):
    return float((text or "0").replace(".", "").replace(",", ".") or 0)


class CreditOpeningImport(models.TransientModel):
    """Fill the opening balance from the last EFD Contribuicoes transmitted by the
    previous system: it reads only the registers 1100 and 1500, which control the
    credit of the earlier periods, and the period of the file."""

    _name = "l10n_br_pis_cofins.credit.opening.import"
    _description = "Importar saldo inicial de crédito da EFD Contribuições"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
    )
    file = fields.Binary(
        string="Arquivo da última EFD Contribuições",
        required=True,
        help="O arquivo (.txt) da última EFD Contribuições transmitida pelo sistema "
        "anterior. Só os registros 1100 e 1500 são lidos: o saldo de cada período de "
        "origem e tipo de crédito, como ficou no fim daquele arquivo.",
    )
    filename = fields.Char()

    def _read_registers(self):
        self.ensure_one()
        text = base64.b64decode(self.file).decode("latin-1")
        period_end = None
        rows = []
        for line in text.splitlines():
            fields_ = line.strip().split("|")
            if len(fields_) < 3:
                continue
            register = fields_[1]
            if register == "0000" and len(fields_) > 7:
                period_end = datetime.strptime(fields_[7], "%d%m%Y").date()
            elif register in REGISTER_TAX and len(fields_) > SLD_CRED_FIM:
                rows.append((REGISTER_TAX[register], fields_))
        return period_end, rows

    def action_import(self):
        """Create one opening balance for each layer of the file that still has
        balance, valid from the month after the period of the file."""
        self.ensure_one()
        period_end, rows = self._read_registers()
        if not period_end:
            raise UserError(
                _("The file is not an EFD Contribuicoes: the record 0000 is missing.")
            )
        cutoff = (period_end.replace(day=1) + timedelta(days=32)).replace(day=1)
        opening = self.env["l10n_br_pis_cofins.credit.opening"]
        created = opening
        for tax_domain, row in rows:
            balance = _number(row[SLD_CRED_FIM])
            if balance <= 0:
                continue
            period = row[PER_APU_CRED]
            amount = _number(row[VL_TOT_CRED_APU])
            created |= opening.create(
                {
                    "company_id": self.company_id.id,
                    "tax_domain": tax_domain,
                    "cutoff_date": cutoff,
                    "origin_period": date(int(period[2:]), int(period[:2]), 1),
                    "cod_cred": row[COD_CRED],
                    "orig_cred": row[ORIG_CRED] or "01",
                    "cnpj_suc": row[CNPJ_SUC] or False,
                    "amount": amount,
                    "used_before": round(amount - balance, 2),
                }
            )
        if not created:
            raise UserError(
                _(
                    "The file has no credit balance in the registers 1100 and 1500 "
                    "to carry to the system."
                )
            )
        return {
            "type": "ir.actions.act_window",
            "res_model": opening._name,
            "view_mode": "tree,form",
            "domain": [("id", "in", created.ids)],
            "name": _("Opening balance of the PIS/COFINS credit"),
        }
