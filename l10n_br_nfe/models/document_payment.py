# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

# pylint: disable=consider-merging-classes-inherited

from odoo import models

from odoo.addons.l10n_br_fiscal_edi.tools import EdiInstallment, EdiPayment


class Document(models.Model):
    _inherit = "l10n_br_fiscal.document"

    def _edi_get_installments(self):
        """The duplicates (``dup``) declared in the collection of the NF-e."""
        self.ensure_one()
        installments = [
            EdiInstallment(
                number=dup.nfe40_nDup or "",
                date_due=dup.nfe40_dVenc,
                amount=dup.nfe40_vDup,
            )
            for dup in self.nfe40_dup
        ]
        return installments or super()._edi_get_installments()

    def _edi_get_payments(self):
        """The payments (``detPag``) declared in the NF-e."""
        self.ensure_one()
        payments = [
            EdiPayment(
                means=payment.nfe40_tPag or "",
                amount=payment.nfe40_vPag,
                term="installments" if payment.nfe40_indPag == "1" else "cash",
                description=payment.nfe40_xPag or "",
            )
            for payment in self.nfe40_detPag
        ]
        return payments or super()._edi_get_payments()
