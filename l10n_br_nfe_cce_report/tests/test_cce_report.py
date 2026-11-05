# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from pathlib import Path

from odoo.tests import TransactionCase, tagged

SAMPLES = Path(__file__).resolve().parent / "samples"
REPORT = "l10n_br_nfe_cce_report.action_report_cce"


def _sample(name):
    return (SAMPLES / name).read_text(encoding="utf-8")


@tagged("post_install", "-at_install")
class TestCCeReport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document = cls.env.ref("l10n_br_nfe.demo_nfe_same_state")
        # o evento fiscal exige o número do documento; a NF-e demo não tem
        cls.document.document_number = "123"
        # sem layout na empresa do usuário, report_action devolve o
        # assistente de layout do Odoo em vez do relatório
        layout = cls.env.ref("web.external_layout_standard")
        cls.env.company.external_report_layout_id = layout
        cls.document.company_id.external_report_layout_id = layout
        cls.document.authorization_file_id = cls.env["ir.attachment"].create(
            {
                "name": "nfe-proc.xml",
                "raw": _sample("nfe-proc.xml").encode("utf-8"),
                "mimetype": "application/xml",
            }
        )
        cls.cce = cls._create_event("14", _sample("cce-envio.xml"))
        cls.cce.set_done(
            status_code="135",
            response="Evento registrado e vinculado a NF-e",
            protocol_date="2026-09-10 00:28:34",
            protocol_number="135260000000002",
            file_response_xml=_sample("cce-retorno.xml"),
        )

    @classmethod
    def _create_event(cls, event_type, xml):
        return cls.env["l10n_br_fiscal.event"].create_event_save_xml(
            company_id=cls.document.company_id,
            environment="prod",
            event_type=event_type,
            xml_file=xml,
            document_id=cls.document,
            sequence="1",
            justification="Justificativa de teste com mais de 15 caracteres",
        )

    def test_print_button_uses_cce_report(self):
        action = self.cce.print_document_event()
        self.assertEqual(action["report_name"], "l10n_br_nfe_cce_report.report_cce")

    def test_print_button_keeps_other_events(self):
        event = self._create_event("2", "<xml/>")
        action = event.print_document_event()
        self.assertEqual(
            action["report_name"], "l10n_br_fiscal_edi.main_report_document_event"
        )

    def test_render_pdf(self):
        pdf, report_format = self.env["ir.actions.report"]._render_qweb_pdf(
            REPORT, self.cce.ids
        )
        self.assertEqual(report_format, "pdf")
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_data_from_xml(self):
        data = self.env["ir.actions.report"]._cce_data(self.cce)
        self.assertEqual(data["event"]["protocol"], "135260000000002")
        self.assertEqual(data["event"]["dh_reg"], "09/09/2026 21:28:34")
        self.assertEqual(data["dest"]["id"], "ESX00000000")
        self.assertIn("TRANSPORTADORA", data["correction"])

    def test_render_without_xml(self):
        event = self._create_event("14", "<xml/>")
        pdf, __ = self.env["ir.actions.report"]._render_qweb_pdf(REPORT, event.ids)
        self.assertTrue(pdf.startswith(b"%PDF"))
