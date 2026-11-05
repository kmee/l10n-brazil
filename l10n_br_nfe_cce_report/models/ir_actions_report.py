# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import base64

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..report.cce_pdf import collect_data, render_cce_pdf

REPORT_CCE = "l10n_br_nfe_cce_report.report_cce"


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_html(self, report_ref, res_ids, data=None):
        if self._get_report(report_ref).report_name == REPORT_CCE:
            return b"", "html"
        return super()._render_qweb_html(report_ref, res_ids, data=data)

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        if self._get_report(report_ref).report_name != REPORT_CCE:
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

        events = self.env["l10n_br_fiscal.event"].browse(res_ids).exists()
        if not events:
            raise UserError(_("No correction letter to print."))
        pages = [(self._cce_data(event), self._cce_logo(event)) for event in events]
        return render_cce_pdf(pages), "pdf"

    def _cce_data(self, event):
        if event.type != "14":
            raise UserError(_("Only correction letters (CC-e) can be printed here."))
        doc = event.document_id.sudo()
        nfe_file = doc.authorization_file_id or doc.send_file_id
        fallback = {
            "key": doc.document_key,
            "dh_emi": self._cce_utc_iso(doc.document_date),
            "nfe_protocol": doc.authorization_protocol,
            "nfe_protocol_date": self._cce_wall_clock_iso(doc.authorization_date),
            "emit_name": event.company_id.legal_name or event.company_id.name,
            "emit_vat": event.company_id.partner_id.vat,
            "dest_name": doc.partner_id.legal_name or doc.partner_id.name,
            "dest_vat": doc.partner_id.vat,
            "tp_amb": {"prod": "1", "hml": "2"}.get(event.environment),
            "sequence": event.sequence,
            "status_code": event.status_code,
            "response": event.response,
            "protocol_number": event.protocol_number,
            "protocol_date": self._cce_wall_clock_iso(event.protocol_date),
            "justification": event.justification,
        }
        return collect_data(
            nfe_file.raw if nfe_file else None,
            event.sudo().file_request_id.raw,
            event.sudo().file_response_id.raw,
            fallback,
        )

    @staticmethod
    def _cce_utc_iso(value):
        """Datetime do Odoo (UTC sem fuso) -> ISO com offset, para o PDF
        converter para o horário de Brasília como faz com o XML."""
        if not value:
            return ""
        return fields.Datetime.to_datetime(value).isoformat() + "+00:00"

    @staticmethod
    def _cce_wall_clock_iso(value):
        """authorization_date e protocol_date: a l10n_br_nfe grava a hora da
        SEFAZ descartando o offset (fromisoformat + to_string), então o valor
        já é o horário de Brasília. Vai sem offset para não ser convertido."""
        if not value:
            return ""
        return fields.Datetime.to_datetime(value).isoformat()

    def _cce_logo(self, event):
        # Mesma regra do DANFE (l10n_br_nfe/report/ir_actions_report.py)
        company = event.company_id
        logo = (
            company.logo if event.document_id.issuer == "company" else company.logo_web
        )
        return base64.b64decode(logo) if logo else None
