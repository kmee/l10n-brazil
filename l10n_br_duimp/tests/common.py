# Copyright (C) 2026 - TODAY, KMEE (<https://kmee.com.br>)
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo.tests import TransactionCase


def duimp_fake_payload():
    """A minimal but structurally-complete DUIMP payload (two items, one
    with per-item taxes) used across the tests. Mirrors the JSON shape
    assumed by the mapping in ``l10n_br_duimp.declaracao`` (still to be
    validated against a real Portal Único response - see B2)."""
    dados_gerais = {
        "identificacao": {
            "numero": "26BR0000758808",
            "versao": 1,
            "situacao": "REGISTRADA",
            "canal": "VERDE",
        },
        "tributos": {
            "tributosCalculados": [
                {"tipo": "II", "valoresBRL": {"devido": 1541.00}},
                {"tipo": "IPI", "valoresBRL": {"devido": 500.00}},
                {"tipo": "PIS", "valoresBRL": {"devido": 210.00}},
                {"tipo": "COFINS", "valoresBRL": {"devido": 970.00}},
            ]
        },
        "pagamentos": [
            {
                "codigoReceita": "0086",
                "nomeTipoPagamento": "II",
                "valorReceita": 1541.00,
                "valorJurosEncargos": 0.0,
                "valorMulta": 0.0,
            }
        ],
    }
    itens = [
        {
            "numeroItem": "1",
            "dadosProduto": {
                "codigoProduto": "DUIMP-BRG-001",
                "codigoNCM": "84821010",
                "descricao": "Imported bearing",
            },
            "itemTributo": {
                "dadosMercadoria": {
                    "quantidadeUnidadeComercializada": 100.0,
                    "unidadeComercializada": "UN",
                },
                "valorMercadoria": {
                    "valorMercadoria": 5000.00,
                    "valorAduaneiro": 5300.00,
                    "valorFreteRateado": 200.00,
                    "valorSeguroRateado": 100.00,
                },
                "calculosTributos": [
                    {
                        "tipo": "II",
                        "baseCalculo": 5300.00,
                        "aliquotaAdValorem": 16.0,
                        "valoresBRL": {"devido": 848.00, "aRecolher": 848.00},
                    },
                ],
            },
        },
        {
            "numeroItem": "2",
            "dadosProduto": {
                "codigoProduto": "DUIMP-SNS-002",
                "codigoNCM": "90258090",
                "descricao": "Imported sensor",
            },
            "itemTributo": {
                "dadosMercadoria": {
                    "quantidadeUnidadeComercializada": 40.0,
                    "unidadeComercializada": "UN",
                },
                "valorMercadoria": {
                    "valorMercadoria": 4800.00,
                    "valorAduaneiro": 4950.00,
                    "valorFreteRateado": 100.00,
                    "valorSeguroRateado": 50.00,
                },
                "calculosTributos": [
                    {
                        "tipo": "II",
                        "baseCalculo": 4950.00,
                        "aliquotaAdValorem": 14.0,
                        "valoresBRL": {"devido": 693.00, "aRecolher": 693.00},
                    },
                ],
            },
        },
    ]
    return dados_gerais, itens


class DuimpCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        cls.dados_gerais, cls.itens = duimp_fake_payload()

        cls.product_1 = cls.env["product.product"].create(
            {
                "name": "Test Imported Bearing",
                "default_code": "DUIMP-BRG-001",
                "type": "product",
            }
        )
        cls.product_2 = cls.env["product.product"].create(
            {
                "name": "Test Imported Sensor",
                "default_code": "DUIMP-SNS-002",
                "type": "product",
            }
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Test Exporter Ltd.", "is_company": True}
        )

    def _create_declaracao(self, afrmm=0.0, siscomex=0.0, capatazia=0.0):
        declaracao = self.env["l10n_br_duimp.declaracao"].create(
            {
                "numero": self.dados_gerais["identificacao"]["numero"],
                "company_id": self.company.id,
                "afrmm_total": afrmm,
                "taxa_siscomex_total": siscomex,
                "capatazia_total": capatazia,
            }
        )
        declaracao._import_from_payload(self.dados_gerais, self.itens)
        return declaracao
