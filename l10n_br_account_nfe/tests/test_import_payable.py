# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import importlib.resources
import re

import nfelib
from nfelib.nfe.bindings.v4_0.leiaute_nfe_v4_00 import TnfeProc

from odoo.tests.common import tagged

from odoo.addons.l10n_br_account.tests.common import AccountMoveBRCommon

ICMS10 = (
    "<ICMS10><orig>0</orig><CST>10</CST><modBC>3</modBC>"
    "<vBC>100.00</vBC><pICMS>18.00</pICMS><vICMS>18.00</vICMS>"
    "<modBCST>4</modBCST><pMVAST>40.00</pMVAST>"
    "<vBCST>140.00</vBCST><pICMSST>18.00</pICMSST><vICMSST>7.20</vICMSST>"
    "<vBCFCPST>140.00</vBCFCPST><pFCPST>2.00</pFCPST><vFCPST>2.80</vFCPST>"
    "</ICMS10>"
)


@tagged("post_install", "-at_install")
class TestImportedNfePayable(AccountMoveBRCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document_type_55 = cls.env.ref("l10n_br_fiscal.document_55")
        if "l10n_latam.document.type" in cls.env:
            cls._mirror_latam_document_type(cls.document_type_55)
        cls.operation = cls.env.ref("l10n_br_fiscal.fo_compras")
        cls.operation_line = cls.env.ref("l10n_br_fiscal.fo_compras_compras")

    def _import_bill(self, with_icms_st):
        res_items = (
            "nfe",
            "samples",
            "v4_0",
            "leiauteNFe",
            "35180834128745000152550010000474281920007498-nfe.xml",
        )
        xml = (
            importlib.resources.files(nfelib.__name__)
            .joinpath(*res_items)
            .read_bytes()
            .decode()
        )
        if with_icms_st:
            xml = re.sub(r"<ICMS00>.*?</ICMS00>", ICMS10, xml, count=1, flags=re.S)
            # the DIFAL group of the sample would overwrite the FCP of the ICMS
            xml = re.sub(r"<ICMSUFDest>.*?</ICMSUFDest>", "", xml, count=1, flags=re.S)
        # without the installments of the file, the payable comes from the taxes
        xml = re.sub(r"<cobr>.*?</cobr>", "", xml, flags=re.S)
        document = (
            self.env["l10n_br_fiscal.document"]
            .sudo()
            .with_context(allow_product_creation=True)
            .import_binding_nfe(TnfeProc.from_xml(xml), edoc_type="in", dry_run=False)
        )
        document.write({"fiscal_operation_id": self.operation.id})
        document.fiscal_line_ids.write(
            {
                "fiscal_operation_id": self.operation.id,
                "fiscal_operation_line_id": self.operation_line.id,
            }
        )
        move = (
            self.env["account.move"]
            .sudo()
            .import_fiscal_document(document, move_type="in_invoice")
        )
        return document, self.env["account.move"].sudo().browse(move.id)

    def _assert_payable_is_the_total(self, document, move):
        payable = sum(
            move.line_ids.filtered(
                lambda line: line.display_type == "payment_term"
            ).mapped("credit")
        )
        self.assertAlmostEqual(payable, document.amount_financial_total, places=2)
        self.assertAlmostEqual(move.amount_residual, move.amount_total, places=2)

    def test_the_payable_of_an_imported_nfe_is_the_total(self):
        document, move = self._import_bill(with_icms_st=False)

        self._assert_payable_is_the_total(document, move)

    def test_the_payable_of_an_imported_nfe_with_icms_st_and_fcp_st_is_the_total(self):
        document, move = self._import_bill(with_icms_st=True)

        self.assertAlmostEqual(
            sum(document.fiscal_line_ids.mapped("icmsst_value")), 7.2, places=2
        )
        self.assertAlmostEqual(
            sum(document.fiscal_line_ids.mapped("icmsfcpst_value")), 2.8, places=2
        )
        self._assert_payable_is_the_total(document, move)
