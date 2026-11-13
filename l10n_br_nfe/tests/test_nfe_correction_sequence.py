# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from odoo.addons.l10n_br_fiscal.constants.fiscal import EVENT_ENV_HML
from odoo.addons.l10n_br_fiscal_edi.constants.fiscal import DOCUMENT_STATE_AUTHORIZED

KEY = "35200181583054000129550010000000052062777166"


class TestNFeCorrectionSequence(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.document = cls.env["l10n_br_fiscal.document"].create(
            {
                "document_type_id": cls.env.ref("l10n_br_fiscal.document_55").id,
                "fiscal_operation_type": "out",
                "document_key": KEY,
                "document_number": "5",
                "nfe_environment": "2",
            }
        )
        cls.document.company_id.processador_edoc = "oca"
        cls.document.write({"state_edoc": DOCUMENT_STATE_AUTHORIZED})

    def _known_correction(self, sequence):
        event = self.document.event_ids.create_event_save_xml(
            company_id=self.document.company_id,
            environment=EVENT_ENV_HML,
            event_type="14",
            xml_file="<envEvento/>",
            document_id=self.document,
            sequence=str(sequence),
        )
        event.set_done("135", "ok", False, "135200000000099", False)
        return event

    def _processor(self):
        processor = MagicMock()
        processor.carta_correcao.return_value = "evento"
        processor.enviar_lote_evento.return_value = SimpleNamespace(
            envio_xml=b"<envEvento/>",
            resposta=SimpleNamespace(
                cStat="128",
                xMotivo="Lote de evento processado",
                retEvento=[
                    SimpleNamespace(
                        infEvento=SimpleNamespace(
                            chNFe=KEY,
                            cStat="135",
                            xMotivo="Evento registrado",
                            dhRegEvento="2026-01-01T10:00:00-03:00",
                            nProt="135200000000001",
                        )
                    )
                ]
            ),
            retorno=SimpleNamespace(content=b"<retEnvEvento/>"),
        )
        return processor

    def _send_correction(self, **context):
        processor = self._processor()
        document = self.document.with_context(**context)
        with patch.object(type(document), "_edoc_processor", return_value=processor):
            document._nfe_correction("Correction of additional data")
        return processor.carta_correcao.call_args.kwargs["sequencia"]

    def test_first_correction_is_sequence_one(self):
        self.assertEqual(self._send_correction(), "1")

    def test_sequence_follows_the_letters_known_by_odoo(self):
        self._known_correction(1)
        self._known_correction(2)
        self.assertEqual(self._send_correction(), "3")

    def test_sequence_continues_letters_issued_outside_odoo(self):
        """Two letters were issued in the previous ERP: the user informs 3."""
        self.assertEqual(self._send_correction(correction_sequence=3), "3")

    def test_wizard_proposes_the_next_sequence_and_sends_the_chosen_one(self):
        self._known_correction(1)
        wizard = self.env["l10n_br_fiscal.document.correction.wizard"].create(
            {
                "document_id": self.document.id,
                "justification": "Correction of additional data",
            }
        )
        self.assertEqual(wizard.correction_sequence, 2)
        wizard.correction_sequence = 4
        processor = self._processor()
        with patch.object(
            type(self.document), "_edoc_processor", return_value=processor
        ):
            wizard.doit()
        self.assertEqual(processor.carta_correcao.call_args.kwargs["sequencia"], "4")
        self.assertIn("4", self.document.correction_event_ids.mapped("sequence"))

    def test_sequence_already_used_is_refused(self):
        self._known_correction(2)
        with self.assertRaises(UserError):
            self._send_correction(correction_sequence=2)

    def test_sequence_above_sefaz_limit_is_refused(self):
        with self.assertRaises(UserError):
            self._send_correction(correction_sequence=21)
