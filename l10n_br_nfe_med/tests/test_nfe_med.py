# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import importlib.resources

import nfelib
from nfelib.nfe.bindings.v4_0.leiaute_nfe_v4_00 import TnfeProc

from odoo.exceptions import UserError, ValidationError

from odoo.addons.l10n_br_nfe_rastro.tests.common import NFE_NS, NFeRastroCommon

SAMPLE = (
    "nfe",
    "samples",
    "v4_0",
    "leiauteNFe",
    "35180834128745000152550010000474281920007498-nfe.xml",
)


class TestNFeMed(NFeRastroCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.med = cls.env["nfe.40.med"].create(
            {"nfe40_cProdANVISA": "1234567890123", "nfe40_vPMC": 25.9}
        )
        cls.product.nfe40_med = cls.med
        d = cls._date
        cls.lot = cls._create_lot(
            "MED-LOT-1", cls._datetime(d(2026, 1, 10)), cls._datetime(d(2027, 1, 31))
        )
        cls._add_stock(cls.lot, 10)

    def _medicine_invoice_without_lots(self):
        """A medicine that is not tracked by lot: the invoice line gets the
        medicine group but no traceability group."""
        product = self.env.ref("product.product_product_12").copy(
            {"name": "Untracked Medicine", "default_code": "MED-NOLOT"}
        )
        product.nfe40_med = self.med
        self.env["stock.quant"].with_company(self.company)._update_available_quantity(
            product, self.stock_location, 5
        )
        picking = self._ship(product, {self.env["stock.lot"]: 2})
        return self._invoice(picking)

    def test_line_gets_medicine_group_from_product(self):
        picking = self._ship(self.product, {self.lot: 2})
        line = self._invoice(picking).invoice_line_ids.filtered(
            lambda ln: ln.product_id == self.product
        )
        self.assertEqual(line.nfe40_med, self.med)

    def test_nfe_xml_has_med_and_rastro(self):
        picking = self._ship(self.product, {self.lot: 2})
        invoice = self._invoice(picking)
        invoice.action_post()
        document = invoice.fiscal_document_id
        self.assertEqual(document.state_edoc, "a_enviar")
        self.assertFalse(document.xml_error_message)
        prod = next(
            p
            for p in self._xml_det_prod(document)
            if p.findtext("nfe:cProd", namespaces=NFE_NS) == "TRACED-1"
        )
        self.assertEqual(
            prod.findtext("nfe:med/nfe:cProdANVISA", namespaces=NFE_NS),
            "1234567890123",
        )
        self.assertEqual(prod.findtext("nfe:med/nfe:vPMC", namespaces=NFE_NS), "25.90")
        self.assertEqual(
            prod.findtext("nfe:rastro/nfe:nLote", namespaces=NFE_NS), "MED-LOT-1"
        )

    def test_medicine_without_rastro_blocks_confirmation(self):
        """Rule K01-20 (rejection 873)."""
        invoice = self._medicine_invoice_without_lots()
        with self.assertRaisesRegex(UserError, "Untracked Medicine.*is required"):
            invoice.action_post()

    def test_k01_20_exceptions(self):
        invoice = self._medicine_invoice_without_lots()
        line = invoice.invoice_line_ids.fiscal_document_line_id
        document = invoice.fiscal_document_id
        self.assertTrue(line._nfe40_rastro_is_required())
        document.ind_pres = "2"
        self.assertFalse(line._nfe40_rastro_is_required())
        document.ind_pres = "1"
        document.edoc_purpose = "4"
        self.assertFalse(line._nfe40_rastro_is_required())
        document.edoc_purpose = "1"
        self.assertTrue(line._nfe40_rastro_is_required())
        line.cfop_id = self.env["l10n_br_fiscal.cfop"].search(
            [("code", "=", "5922")], limit=1
        )
        self.assertFalse(line._nfe40_rastro_is_required())

    def test_anvisa_code_pattern(self):
        for code in ("12345678901", "ISENTO"):
            self.env["nfe.40.med"].create({"nfe40_cProdANVISA": code})
        for code in ("123", "isento", "123456789012"):
            with self.assertRaises(ValidationError):
                self.env["nfe.40.med"].create({"nfe40_cProdANVISA": code})

    def test_import_supplier_nfe_keeps_med(self):
        xml = (
            importlib.resources.files(nfelib.__name__)
            .joinpath(*SAMPLE)
            .read_bytes()
            .decode()
        )
        med = (
            "<med><cProdANVISA>ISENTO</cProdANVISA>"
            "<xMotivoIsencao>RDC 98/2016</xMotivoIsencao>"
            "<vPMC>12.50</vPMC></med>"
        )
        xml = xml.replace(
            "<indTot>1</indTot>\n        </prod>",
            f"<indTot>1</indTot>{med}</prod>",
            1,
        )
        document = self.env["l10n_br_fiscal.document"].import_binding_nfe(
            TnfeProc.from_xml(xml), edoc_type="in", dry_run=False
        )
        line = document.fiscal_line_ids.filtered(lambda ln: ln.nfe40_cProd == "1208")
        self.assertEqual(
            (
                line.nfe40_med.nfe40_cProdANVISA,
                line.nfe40_med.nfe40_xMotivoIsencao,
                line.nfe40_med.nfe40_vPMC,
            ),
            ("ISENTO", "RDC 98/2016", 12.5),
        )
