# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo import models

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    EDOC_PURPOSE_COMPLEMENTAR,
    FISCAL_IN,
    SITUACAO_FISCAL_CANCELADO,
    SITUACAO_FISCAL_COMPLEMENTAR,
    SITUACAO_FISCAL_COMPLEMENTAR_EXTEMPORANEO,
    SITUACAO_FISCAL_DENEGADO,
    SITUACAO_FISCAL_INUTILIZADO,
    SITUACAO_FISCAL_REGULAR,
    SITUACAO_FISCAL_REGULAR_EXTEMPORANEO,
    SITUACAO_FISCAL_SPED_CONSIDERA_CANCELADO,
)

# state_edoc -> SPED document situation (table 4.1.2 of the EFD ICMS/IPI and
# EFD Contribuicoes guides). Anything else (draft, in the middle of the
# transmission) is not a document the books must carry.
SPED_COD_SIT_BY_STATE_EDOC = {
    "autorizada": SITUACAO_FISCAL_REGULAR,
    "cancelada": SITUACAO_FISCAL_CANCELADO,
    "denegada": SITUACAO_FISCAL_DENEGADO,
    "inutilizada": SITUACAO_FISCAL_INUTILIZADO,
}

# IND_PGTO of the C100: a vista, a prazo, sem pagamento
SPED_IND_PGTO_CASH = "0"
SPED_IND_PGTO_TERM = "1"
SPED_IND_PGTO_NONE = "9"

# the active situations that have an "escriturado depois" twin
SPED_COD_SIT_EXTEMPORANEO = {
    SITUACAO_FISCAL_REGULAR: SITUACAO_FISCAL_REGULAR_EXTEMPORANEO,
    SITUACAO_FISCAL_COMPLEMENTAR: SITUACAO_FISCAL_COMPLEMENTAR_EXTEMPORANEO,
}


class FiscalDocument(models.Model):
    _inherit = "l10n_br_fiscal.document"

    def _get_sped_cod_sit(self, period_start=None):
        """COD_SIT of the C100 of this document, shared by every SPED.

        ``state_fiscal`` is only written when a document is cancelled, so it
        cannot be the only source: when it is empty the situation comes from
        the state of the document (``state_edoc``) and from its purpose
        (complementary). An entry booked in a period after the one of its
        emission is "extemporaneo" (01 regular, 07 complementary).

        :param period_start: first day of the declaration period.
        """
        self.ensure_one()
        if self.state_fiscal:
            return self.state_fiscal
        cod_sit = SPED_COD_SIT_BY_STATE_EDOC.get(
            self.state_edoc, SITUACAO_FISCAL_REGULAR
        )
        if cod_sit == SITUACAO_FISCAL_REGULAR:
            if self.edoc_purpose == EDOC_PURPOSE_COMPLEMENTAR:
                cod_sit = SITUACAO_FISCAL_COMPLEMENTAR
            if (
                period_start
                and self.fiscal_operation_type == FISCAL_IN
                and self.document_date
                and self.document_date.date() < period_start
            ):
                cod_sit = SPED_COD_SIT_EXTEMPORANEO[cod_sit]
        return cod_sit

    def _is_sped_cancelled(self):
        """Cancelled, denied and unused numbers carry no values, no items and no
        analytic registers (Guia Pratico, C100)."""
        self.ensure_one()
        return self._get_sped_cod_sit() in SITUACAO_FISCAL_SPED_CONSIDERA_CANCELADO

    def _get_sped_ind_pgto(self):
        """IND_PGTO of the C100 (and of the A100), shared by every SPED: 0 paid
        on the spot, 1 on terms, 9 without payment (Guia Pratico). It comes from
        the installments of the bill of the document: all due on the emission
        date is "a vista", any later one is "a prazo", no installment is "sem
        pagamento"."""
        self.ensure_one()
        # move_ids comes from l10n_br_account, which both SPED modules depend on
        moves = (
            self.move_ids if "move_ids" in self._fields else self.env["account.move"]
        )
        terms = moves.filtered(lambda move: move.state != "cancel").line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )
        if not terms:
            return SPED_IND_PGTO_NONE
        invoice_date = self.document_date and self.document_date.date()
        if all(
            not line.date_maturity
            or not invoice_date
            or line.date_maturity <= invoice_date
            for line in terms
        ):
            return SPED_IND_PGTO_CASH
        return SPED_IND_PGTO_TERM
