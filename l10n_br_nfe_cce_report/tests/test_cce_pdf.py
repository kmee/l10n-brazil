"""Teste do layout fora do Odoo (só fpdf2 + lxml).

    python l10n_br_nfe_cce_report/tests/test_cce_pdf.py [saida.pdf]

O `tests/__init__.py` não importa este arquivo: o Odoo não o carrega.
Dados fictícios, em `tests/samples/`.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "cce_pdf", Path(__file__).resolve().parent.parent / "report" / "cce_pdf.py"
)
cce_pdf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cce_pdf)

SAMPLES = Path(__file__).resolve().parent / "samples"
KEY = "35260911222333000181550010000001231000001234"
NFE_XML = (SAMPLES / "nfe-proc.xml").read_text(encoding="utf-8")
EVENT_REQUEST = (SAMPLES / "cce-envio.xml").read_text(encoding="utf-8")
# Retorno como vem do webservice: envelope SOAP em volta do retEnvEvento.
EVENT_RESPONSE = (SAMPLES / "cce-retorno.xml").read_text(encoding="utf-8")


class TestCCePDF(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.data = cce_pdf.collect_data(NFE_XML, EVENT_REQUEST, EVENT_RESPONSE)

    def test_fields(self):
        d = self.data
        self.assertEqual(d["key"], KEY)
        self.assertEqual(d["nfe"]["number"], "123")
        self.assertEqual(d["nfe"]["month_year"], "09/2026")
        self.assertEqual(d["nfe"]["dh_emi"], "09/09/2026 21:08:26")
        self.assertEqual(d["nfe"]["protocol"], "135260000000001 - 09/09/2026 21:19:28")
        self.assertEqual(d["emit"]["cnpj"], "11.222.333/0001-81")
        self.assertEqual(d["emit"]["zip"], "12010-000")
        self.assertEqual(d["dest"]["id_label"], "IDENTIFICAÇÃO (ID ESTRANGEIRO)")
        self.assertEqual(d["dest"]["id"], "ESX00000000")
        self.assertEqual(d["dest"]["country"], "Espanha")
        self.assertEqual(d["event"]["type"], "110110 - Carta de Correção")
        self.assertEqual(d["event"]["organ"], "35 - SP")
        self.assertEqual(d["event"]["environment"], "PRODUÇÃO")
        self.assertEqual(
            d["event"]["status"], "135 - Evento registrado e vinculado a NF-e"
        )
        self.assertEqual(d["event"]["protocol"], "135260000000002")
        self.assertEqual(d["event"]["dh_reg"], "09/09/2026 21:28:34")
        self.assertIn("TRANSPORTADORA", d["correction"])

    def test_fallback_without_xml(self):
        d = cce_pdf.collect_data(
            None,
            None,
            None,
            {"key": KEY, "justification": "Texto da correcao", "tp_amb": "2"},
        )
        self.assertEqual(d["nfe"]["number"], "123")
        self.assertEqual(d["event"]["environment"], "HOMOLOGAÇÃO")
        self.assertEqual(d["correction"], "Texto da correcao")
        self.assertTrue(d["cond_uso"])

    def test_utc_converted_to_brasilia(self):
        self.assertEqual(
            cce_pdf.format_datetime("2026-09-10T00:28:34+00:00"),
            "09/09/2026 21:28:34",
        )
        self.assertEqual(
            cce_pdf.format_month_year("2026-10-01T01:00:00+00:00"), "09/2026"
        )

    def test_fallback_dates(self):
        # Como o Odoo manda: document_date em UTC com offset; datas de
        # protocolo já no horário de Brasília, sem offset.
        d = cce_pdf.collect_data(
            None,
            None,
            None,
            {
                "key": KEY,
                "dh_emi": "2026-09-10T03:08:26+00:00",
                "nfe_protocol": "135263776844498",
                "nfe_protocol_date": "2026-09-10T00:19:28",
                "protocol_date": "2026-09-10T00:28:34",
            },
        )
        self.assertEqual(d["nfe"]["dh_emi"], "10/09/2026 00:08:26")
        self.assertEqual(d["nfe"]["protocol"], "135263776844498 - 10/09/2026 00:19:28")
        self.assertEqual(d["event"]["dh_reg"], "10/09/2026 00:28:34")

    def test_cond_uso_accented_when_standard_text(self):
        # texto exato do xCondUso da SEFAZ (sem acento, como vem no XML)
        sefaz = (
            "A Carta de Correcao e disciplinada pelo paragrafo 1o-A do art. 7o do "
            "Convenio S/N, de 15 de dezembro de 1970 e pode ser utilizada para "
            "regularizacao de erro ocorrido na emissao de documento fiscal, desde "
            "que o erro nao esteja relacionado com: I - as variaveis que determinam "
            "o valor do imposto tais como: base de calculo, aliquota, diferenca de "
            "preco, quantidade, valor da operacao ou da prestacao; II - a correcao "
            "de dados cadastrais que implique mudanca do remetente ou do "
            "destinatario; III - a data de emissao ou de saida."
        )
        text = cce_pdf.cond_uso_text(sefaz)
        self.assertIn("Correção é disciplinada pelo parágrafo 1º-A", text)
        self.assertIn("data de emissão ou de saída.", text)

    def test_cond_uso_other_text_kept_as_is(self):
        self.assertEqual(cce_pdf.cond_uso_text("Outro texto"), "Outro texto")

    def test_address_without_double_comma(self):
        xml = NFE_XML.replace(
            "<xLgr>Rua das Flores</xLgr>", "<xLgr>Rua das Flores,</xLgr>"
        )
        data = cce_pdf.collect_data(xml, EVENT_REQUEST, EVENT_RESPONSE)
        self.assertEqual(data["emit"]["address"], "Rua das Flores, 100")

    def test_fallback_with_odoo_false_values(self):
        # campos vazios do Odoo chegam como False (ex.: NF-e sem chave)
        d = cce_pdf.collect_data(None, None, None, {"key": False, "sequence": False})
        self.assertEqual(d["key"], "")

    def test_render(self):
        pdf = cce_pdf.render_cce_pdf([(self.data, None)])
        self.assertTrue(pdf.startswith(b"%PDF"))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].endswith(".pdf"):
        out = Path(sys.argv.pop(1))
        data = cce_pdf.collect_data(NFE_XML, EVENT_REQUEST, EVENT_RESPONSE)
        out.write_bytes(cce_pdf.render_cce_pdf([(data, None)]))
        sys.stdout.write(f"PDF gravado em {out}\n")
    unittest.main()
