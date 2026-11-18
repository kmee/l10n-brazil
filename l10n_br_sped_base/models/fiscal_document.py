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

    def _has_sped_c100(self):
        """Does this document go into the C100 (and its children)?

        A denied note and an unused number do not: the situation codes 04
        (denied) and 05 (unused number) of the table 4.1.2 were discontinued in
        the Guia Pratico from 01/2023 and the information is no longer
        required. A cancelled note still goes in, with COD_SIT 02. The one place
        to bring the old codes back is this method (return True).
        """
        self.ensure_one()
        return self._get_sped_cod_sit() not in (
            SITUACAO_FISCAL_DENEGADO,
            SITUACAO_FISCAL_INUTILIZADO,
        )

    def _is_sped_cancelled(self):
        """Cancelled, denied and unused numbers carry no values, no items and no
        analytic registers (Guia Pratico, C100)."""
        self.ensure_one()
        return self._get_sped_cod_sit() in SITUACAO_FISCAL_SPED_CONSIDERA_CANCELADO
