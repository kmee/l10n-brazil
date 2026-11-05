# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models

EVENT_TYPE_CCE = "14"


class FiscalEvent(models.Model):
    _inherit = "l10n_br_fiscal.event"

    def _is_nfe_cce(self):
        return all(
            event.type == EVENT_TYPE_CCE and event.document_id.document_type == "55"
            for event in self
        )

    def print_document_event(self):
        if self and self._is_nfe_cce():
            return self.env.ref(
                "l10n_br_nfe_cce_report.action_report_cce"
            ).report_action(self)
        return super().print_document_event()
