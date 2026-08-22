# Copyright (C) 2026-Today - KMEE (<http://kmee.com.br>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""Testes golden do payload de remessa enviado ao BRCobrança.

Os bytes da remessa são gerados pela lib Ruby, mas tudo o que o Odoo controla
- e onde estão as particularidades de banco e de carteira - é o payload JSON
enviado para ela. Congelar esse payload por banco/formato cobre 100% da parte
que é nossa e roda sem o serviço externo, ao contrário dos demais testes deste
módulo (que são pulados com ``CI_NO_BRCOBRANCA``).

Para semear ou atualizar os arquivos de ``tests/golden``, veja
``l10n_br_account_payment_order/tests/golden.py``.
"""

from pathlib import Path

from odoo import fields
from odoo.tests import tagged

from odoo.addons.l10n_br_account_payment_order.tests.golden import GoldenMixin

from ..constants.br_cobranca import get_brcobranca_bank
from .common import TestBRCobrancaCommon

# Valores fixados para que o payload seja determinístico. Não são arbitrários:
# o nosso número com 8 dígitos exercita o corte para 7 + DV do Santander 400 e
# o número do documento com 11 dígitos exercita o corte para 10 do Unicred.
PINNED_DATE = "2024-03-15"
PINNED_OWN_NUMBER = "1000000%s"
PINNED_DOC_NUMBER = "9000000000%s"
PINNED_FILE_NUMBER = 1


@tagged("post_install", "-at_install")
class TestGoldenRemessa(GoldenMixin, TestBRCobrancaCommon):
    """Uma remessa congelada por banco e formato.

    A regra de leitura de um PR aqui é simples: se o diff mexe no golden de um
    banco que o PR não se propôs a alterar, ou é bug ou é mudança de base.
    """

    def _golden_dir(self):
        return Path(__file__).parent / "golden"

    def _open_payment_order(self, invoice):
        """Leva a fatura até a ordem de pagamento aberta, sem gerar arquivo."""
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        payment_order = self._get_draft_payment_order(invoice)
        payment_order.draft2open()
        return payment_order

    def _pin_volatile_values(self, payment_order):
        """Fixa o que varia entre execuções (datas, sequências, contadores)."""
        payment_order.file_number = PINNED_FILE_NUMBER
        for index, line in enumerate(payment_order.payment_line_ids, 1):
            line.write(
                {
                    "date": fields.Date.to_date(PINNED_DATE),
                    "own_number": PINNED_OWN_NUMBER % index,
                    "document_number": PINNED_DOC_NUMBER % index,
                }
            )

    def _assert_remessa(self, case, invoice):
        # A ordem é aberta uma vez só; o payload em si é puro, então pode ser
        # remontado quantas vezes o mixin precisar para provar determinismo.
        payment_order = self._open_payment_order(invoice)
        self._pin_volatile_values(payment_order)
        cnab_config = payment_order.payment_mode_id.cnab_config_id
        bank_brcobranca = get_brcobranca_bank(
            payment_order.journal_id.bank_account_id,
            cnab_config.payment_method_id.code,
        )
        self.assert_golden_json(
            case,
            lambda: payment_order._prepare_remessa_payload(
                cnab_config, bank_brcobranca
            ),
        )

    def test_golden_banco_brasil_240(self):
        self._assert_remessa("001_banco_brasil_240", self.invoice_brasil_240)

    def test_golden_banco_brasil_400(self):
        self._assert_remessa("001_banco_brasil_400", self.invoice_brasil_400)

    def test_golden_banco_nordeste_400(self):
        self._assert_remessa("004_banco_nordeste_400", self.invoice_nordeste_400)

    def test_golden_santander_240(self):
        self._assert_remessa("033_santander_240", self.invoice_santander_240)

    def test_golden_santander_400(self):
        self._assert_remessa("033_santander_400", self.invoice_santander_400)

    def test_golden_ailos_240(self):
        self._assert_remessa("085_ailos_240", self.invoice_ailos_240)

    def test_golden_caixa_240(self):
        self._assert_remessa("104_caixa_240", self.invoice_cef_240)

    def test_golden_unicred_400(self):
        self._assert_remessa("136_unicred_400", self.invoice_unicred_400_1)

    def test_golden_bradesco_400(self):
        self._assert_remessa("237_bradesco_400", self.invoice_bradesco_400)

    def test_golden_itau_400(self):
        self._assert_remessa("341_itau_400", self.invoice_itau_400)

    def test_golden_sicredi_240(self):
        self._assert_remessa("748_sicredi_240", self.invoice_sicredi_240)
