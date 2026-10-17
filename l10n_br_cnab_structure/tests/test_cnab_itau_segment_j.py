# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

BOLETO_DIGITABLE_LINE = "00190123435678901234356789012343399010000123456"


@tagged("post_install", "-at_install")
class TestCnabItauSegmentJ(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(
        cls, chart_template_ref="l10n_br_coa_generic.l10n_br_coa_generic_template"
    ):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.company_data["company"]
        cls.company.update({"cnpj_cpf": "82688625000152"})
        cls.env.user.company_id = cls.company.id
        cls.partner_a.update({"cnpj_cpf": "45823449000198"})
        bank = cls.env.ref("l10n_br_base.res_bank_341")
        account = cls.env["res.partner.bank"].create(
            {
                "acc_number": "205040",
                "bra_number": "1030",
                "bank_id": bank.id,
                "company_id": cls.company.id,
                "partner_id": cls.company.partner_id.id,
            }
        )
        journal = cls.env["account.journal"].create(
            {
                "name": "Itau Bank",
                "type": "bank",
                "code": "BNKI",
                "bank_account_id": account.id,
                "bank_id": bank.id,
            }
        )
        mode = cls.env["account.payment.mode"].create(
            {
                "name": "Itau boleto",
                "bank_account_link": "fixed",
                "company_id": cls.company.id,
                "payment_method_id": cls.env.ref(
                    "l10n_br_account_payment_order.payment_mode_type_cnab240_out"
                ).id,
                "payment_mode_domain": "boleto",
                "payment_order_ok": True,
                "fixed_journal_id": journal.id,
                "cnab_structure_id": cls.env.ref(
                    "l10n_br_cnab_structure.cnab_itau_240"
                ).id,
                "cnab_payment_way_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref(
                                "l10n_br_cnab_structure.cnab_itau_240_pay_way_31"
                            ).id
                        ],
                    )
                ],
                "cnab_processor": "oca_processor",
            }
        )
        cls.order = cls.env["account.payment.order"].create(
            {
                "payment_mode_id": mode.id,
                "state": "draft",
                "company_id": cls.company.id,
                "journal_id": journal.id,
            }
        )
        cls.payment_line = cls.env["account.payment.line"].create(
            {
                "order_id": cls.order.id,
                "partner_id": cls.partner_a.id,
                "amount_currency": 1234.0,
                "communication": "BOLETO TEST",
                "barcode": BOLETO_DIGITABLE_LINE,
            }
        )

    def _field(self, xmlid):
        return self.env.ref(f"l10n_br_cnab_structure.{xmlid}")

    def test_segment_j_your_number_is_the_payment_line(self):
        """SEU NUMERO (183-202) sends the payment line and returns as your_number."""
        field = self._field("cnab_itau_240_boleto_segmento_j_183_202")
        self.assertEqual(field.content_source_field, "name")
        self.assertEqual(field.content_dest_field, "your_number")
        value = field.output(self.payment_line)[1]
        self.assertEqual(len(value), 20)
        self.assertEqual(value.strip(), self.payment_line.name)

    def test_segment_j_o_bank_number_returns_as_own_number(self):
        """NOSSO NUMERO (216-230) is sent blank and returns as own_number."""
        for xmlid in (
            "cnab_itau_240_boleto_segmento_j_216_230",
            "cnab_itau_240_conc_tributo_bc_segmento_o_216_230",
        ):
            field = self._field(xmlid)
            self.assertFalse(field.content_source_field)
            self.assertEqual(field.content_dest_field, "own_number")
            self.assertEqual(field.output(self.payment_line)[1], " " * 15)

    def test_segment_j_complement_fields_are_zeros_and_blanks(self):
        """ZEROS (168-182) is numeric and the C/C history of the header is blank."""
        zeros = self._field("cnab_itau_240_boleto_segmento_j_168_182")
        self.assertEqual(zeros.type, "num")
        self.assertEqual(zeros.output(self.payment_line)[1], "0" * 15)
        for xmlid in (
            "cnab_itau_240_conc_tributo_bc_header_133_142",
            "cnab_itau_240_tributo_sem_bc_header_133_142",
        ):
            history = self._field(xmlid)
            self.assertEqual(history.type, "alpha")
            self.assertEqual(history.format(history.size, history.type, ""), " " * 10)

    def test_return_event_without_move_line(self):
        """Linking return events skips payment lines without a move line."""
        self.assertFalse(self.payment_line.move_line_id)
        event = self.env["l10n_br_cnab.return.event"].create(
            {"your_number": self.payment_line.name}
        )
        event.payment_line_ids = self.payment_line
        event.set_move_line_ids()
        self.assertFalse(event.move_line_ids)
