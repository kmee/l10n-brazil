# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

# pylint: disable=consider-merging-classes-inherited

from odoo import _, models


class Document(models.Model):
    """What a fiscal document declares to be paid, and the page that shows it.

    The installments and the payments are read from the document by the module of
    its type (NF-e ``dup`` and ``detPag``, CT-e ``cobr``). Nothing here creates a
    payable: the titles are born when the invoice is generated.
    """

    _inherit = "l10n_br_fiscal.document"

    def _edi_get_installments(self):
        """Installments declared by the document, as a list of ``EdiInstallment``."""
        self.ensure_one()
        return []

    def _edi_get_payments(self):
        """Payments declared by the document, as a list of ``EdiPayment``."""
        self.ensure_one()
        return []

    def _edi_display_installments(self):
        """Installments the page shows. Who knows more than the declaration (the
        invoice that will issue the document) overrides it."""
        self.ensure_one()
        return self._edi_get_installments()

    def _edi_display_payments(self):
        """Payments the page shows."""
        self.ensure_one()
        return self._edi_get_payments()

    def _edi_installment_difference(self):
        """Net amount payable minus the sum of the installments shown."""
        self.ensure_one()
        installments = self._edi_display_installments()
        if not installments:
            return 0.0
        declared = sum(installment.amount for installment in installments)
        return self.currency_id.round(self.amount_financial_total - declared)

    def _edi_installment_warning(self):
        """Message when the installments do not add up to the net amount payable."""
        self.ensure_one()
        if not self._edi_installment_difference():
            return False
        declared = sum(i.amount for i in self._edi_display_installments())
        return _(
            "The declared installments add up to %(declared)s; the net amount "
            "payable is %(net)s. The invoice spreads the difference by the weight "
            "of each installment."
        ) % {
            "declared": f"{declared:.2f}",
            "net": f"{self.amount_financial_total:.2f}",
        }

    def _edi_import_warnings(self):
        messages = super()._edi_import_warnings()
        warning = self._edi_installment_warning()
        if self.imported_document and warning:
            messages.append(warning)
        return messages
