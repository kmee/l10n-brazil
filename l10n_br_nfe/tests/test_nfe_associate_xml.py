# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import importlib.resources

import nfelib

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

SAMPLE_KEY = "35180834128745000152550010000474281920007498"


class TestNfeAssociateXml(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.xml = (
            importlib.resources.files(nfelib.__name__)
            .joinpath("nfe", "samples", "v4_0", "leiauteNFe", f"{SAMPLE_KEY}-nfe.xml")
            .read_bytes()
        )
        cls.nfe = cls.env.ref("l10n_br_nfe.demo_nfe_natural_icms_18_red_51_11")
        cls.nfe.action_document_confirm()

    def _wizard(self):
        return self.env["l10n_br_nfe.associate.xml.wizard"].create(
            {"document_id": self.nfe.id, "xml_file": base64.b64encode(self.xml)}
        )

    def test_associate_authorized_xml(self):
        self.nfe.write({"document_key": SAMPLE_KEY, "document_date": "2018-08-10"})
        self._wizard().action_associate_xml()
        self.assertEqual(self.nfe.state_edoc, "autorizada")
        self.assertEqual(self.nfe.status_code, "100")
        self.assertTrue(self.nfe.authorization_file_id)
        self.assertTrue(self.nfe.authorization_protocol)
        self.assertTrue(self.nfe.file_report_id)

    def test_associate_xml_of_another_key(self):
        with self.assertRaises(UserError):
            self._wizard().action_associate_xml()
        self.assertNotEqual(self.nfe.state_edoc, "autorizada")

    def test_regenerate_danfe(self):
        self.nfe.make_pdf()
        previous = self.nfe.file_report_id
        self.nfe.action_regenerate_danfe()
        self.assertTrue(self.nfe.file_report_id)
        self.assertNotEqual(self.nfe.file_report_id, previous)

    def test_open_associate_xml_wizard(self):
        action = self.nfe.action_open_associate_xml_wizard()
        self.assertEqual(action["context"], {"default_document_id": self.nfe.id})

    def test_associate_invalid_xml(self):
        with self.assertRaises(UserError):
            self.nfe._nfe_associate_authorized_xml(b"not an xml")

    def test_associate_xml_without_authorization_protocol(self):
        self.nfe.write({"document_key": SAMPLE_KEY, "document_date": "2018-08-10"})
        xml = self.xml.replace(b"<cStat>100</cStat>", b"<cStat>110</cStat>")
        with self.assertRaises(UserError):
            self.nfe._nfe_associate_authorized_xml(xml)

    def test_associate_xml_without_authorization_event(self):
        self.nfe.write({"document_key": SAMPLE_KEY, "document_date": "2018-08-10"})
        self.nfe.authorization_event_id = False
        with self.assertRaises(UserError):
            self.nfe._nfe_associate_authorized_xml(self.xml)

    def test_associate_xml_twice(self):
        self.nfe.write({"document_key": SAMPLE_KEY, "document_date": "2018-08-10"})
        self._wizard().action_associate_xml()
        with self.assertRaises(UserError):
            self._wizard().action_associate_xml()
