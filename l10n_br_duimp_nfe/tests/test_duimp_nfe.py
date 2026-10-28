# Copyright (C) 2026 - TODAY, KMEE (<https://kmee.com.br>)
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.l10n_br_duimp.tests.common import DUIMP_NUMBER, DuimpCommon


@tagged("post_install", "-at_install")
class TestDuimpNfe(DuimpCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.declaracao = cls.env["l10n_br_duimp.declaracao"].create(
            {
                "numero": DUIMP_NUMBER,
                "data_registro": "2026-01-15",
                "data_desembaraco": "2026-01-20",
                "urf_despacho_nome": "PORTO DE SANTOS",
                "uf_desembaraco": "SP",
                "via_transporte_codigo": "01",
                "caracterizacao_operacao_codigo": "1",
                "afrmm_total": 1000.0,
                "company_id": cls.company.id,
            }
        )
        cls.declaracao._import_from_payload(cls.dados_gerais, cls.itens)
        cls.item = cls.declaracao.item_ids.filtered(lambda i: i.numero_item == "1")

    def _make_document_line(self):
        document = self.env["l10n_br_fiscal.document"].create(
            {
                "document_type_id": self.env.ref("l10n_br_fiscal.document_55").id,
                "issuer": "company",
            }
        )
        line = self.env["l10n_br_fiscal.document.line"].create(
            {
                "document_id": document.id,
                "product_id": self.product_1.id,
                "duimp_item_id": self.item.id,
            }
        )
        return document, line

    def test_compute_nfe40_di_from_duimp_item(self):
        document, line = self._make_document_line()
        with patch.object(type(document), "_need_compute_nfe_tags", return_value=True):
            line._compute_nfe40_DI_duimp()
        self.assertEqual(len(line.nfe40_DI), 1)
        di_tag = line.nfe40_DI
        self.assertEqual(di_tag.nfe40_nDI, DUIMP_NUMBER)
        self.assertEqual(di_tag.nfe40_xLocDesemb, "PORTO DE SANTOS")
        self.assertEqual(di_tag.nfe40_UFDesemb, "SP")
        self.assertAlmostEqual(di_tag.nfe40_vAFRMM, self.item.amount_afrmm, places=2)
        self.assertEqual(len(di_tag.nfe40_adi), 1)
        self.assertEqual(di_tag.nfe40_adi.nfe40_nAdicao, "1")
        self.assertEqual(di_tag.nfe40_adi.nfe40_nSeqAdic, "1")

    def test_no_duimp_item_no_tag(self):
        document, line = self._make_document_line()
        line.duimp_item_id = False
        with patch.object(type(document), "_need_compute_nfe_tags", return_value=True):
            line._compute_nfe40_DI_duimp()
        self.assertFalse(line.nfe40_DI)

    def test_manual_di_kept_without_duimp_item(self):
        """A line that is not linked to a DUIMP item keeps the DI group that
        was typed in or written by the import declaration wizard of
        l10n_br_account: the DUIMP compute must not clear it."""
        document, line = self._make_document_line()
        line.duimp_item_id = False
        line.nfe40_DI = [
            (
                0,
                0,
                {
                    "nfe40_nDI": "2612345678",
                    "nfe40_dDI": "2026-01-15",
                    "nfe40_xLocDesemb": "SANTOS",
                    "nfe40_dDesemb": "2026-01-20",
                    "nfe40_tpViaTransp": "1",
                    "nfe40_tpIntermedio": "1",
                    "nfe40_cExportador": "EXP",
                },
            )
        ]
        with patch.object(type(document), "_need_compute_nfe_tags", return_value=True):
            line._compute_nfe40_DI_duimp()
            line.invalidate_recordset(["nfe40_DI"])
            self.assertEqual(line.nfe40_DI.nfe40_nDI, "2612345678")
            # a change of the e-document state recomputes the field
            document.state_edoc = "a_enviar"
            self.env.flush_all()
            line.invalidate_recordset(["nfe40_DI"])
            self.assertEqual(line.nfe40_DI.nfe40_nDI, "2612345678")

    def test_di_editable_on_the_line(self):
        """The DI page that l10n_br_nfe puts on the line form stays editable."""
        field = self.env["l10n_br_fiscal.document.line"]._fields["nfe40_DI"]
        self.assertFalse(field.readonly)
