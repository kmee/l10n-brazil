# Copyright (C) 2022 - Engenere (<https://engenere.one>).
# Copyright (C) 2025 Escodoo (https://www.escodoo.com.br)
# @author Antônio S. Pereira Neto <neto@engenere.one>
# @author Kaynnan Lemes <kaynnan.lemes@escodoo.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
from pathlib import Path
from tempfile import TemporaryDirectory

from unidecode import unidecode

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import Form
from odoo.tests.common import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

CNAB_240 = "240"
CNAB_400 = "400"
CNAB_500 = "500"

POS_BANK_START = 1
POS_BANK_END = 3
POS_REC_TYPE = 8
POS_BATCH_START = 4
POS_BATCH_END = 7
POS_WAY_START = 12
POS_WAY_END = 13
POS_DETAIL_START = 9
POS_DETAIL_END = 13
POS_SEGMENT_START = 14
POS_SEGMENT_END = 14

REC_FILE_HEADER = 0
REC_BATCH_HEADER = 1
REC_DETAIL = 3
REC_BATCH_TRAILER = 5
REC_FILE_TRAILER = 9

PAY_WAY_SAME_BANK = "01"
PAY_WAY_OTHER_BANK = "41"

SVC_SUPPLIER = "20"
SVC_SALARY = "30"
# Service type used for employee payments (PIX, TED and same-bank credit).
# Decided by Daniel at GATE 2 (2026-10-06): 20 (Fornecedores) for everyone.
SVC_EMPLOYEE = SVC_SUPPLIER

TEST_CNPJ = "82688625000152"
TEST_PARTNER_CNPJ = "45823449000198"
TEST_INVOICE_AMOUNT = 300.0


def replace_chars(string: str, index: int, replacement: str) -> str:
    return string[:index] + replacement + string[index + len(replacement) :]


@tagged("post_install", "-at_install")
class TestCNABStructure(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        cls.chart_template = "br_oca_generic"
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.company_data["company"]
        cls.company.update({"vat": TEST_CNPJ})
        cls.env.user.company_id = cls.company.id

        cls.res_partner_bank_model = cls.env["res.partner.bank"]
        cls.payment_mode_model = cls.env["account.payment.mode"]
        cls.payment_order_model = cls.env["account.payment.order"]
        cls.payment_line_model = cls.env["account.payment.line"]
        cls.attachment_model = cls.env["ir.attachment"]
        cls.res_partner_pix_model = cls.env["res.partner.pix"]

        cls.bank_341 = cls.env.ref("l10n_br_base.res_bank_341")
        cls.bank_001 = cls.env.ref("l10n_br_base.res_bank_001")
        cls.outbound_payment_method = cls.env.ref(
            "l10n_br_account_payment_order.payment_mode_type_cnab240_out"
        )

        cls.cnab_structure_itau_240 = cls.env.ref(
            "l10n_br_cnab_structure.cnab_itau_240"
        )
        cls.cnab_structure_bb_240 = cls.env.ref("l10n_br_cnab_structure.cnab_bb_240")

        cls._setup_partner_data()
        cls._setup_bank_accounts()
        cls._setup_payment_modes()
        cls._setup_pix_data()

    @classmethod
    def _setup_partner_data(cls):
        cls.partner_a.update({"vat": TEST_PARTNER_CNPJ})

        cls.partner_a_itau_bank = cls.res_partner_bank_model.create(
            {
                "acc_number": "123456",
                "acc_number_dig": "7",
                "bra_number": "0001",
                "bank_id": cls.bank_341.id,
                "partner_id": cls.partner_a.id,
            }
        )
        cls.partner_a_bb_bank = cls.res_partner_bank_model.create(
            {
                "acc_number": "789012",
                "bra_number": "0002",
                "bank_id": cls.bank_001.id,
                "partner_id": cls.partner_a.id,
            }
        )

    @classmethod
    def _setup_bank_accounts(cls):
        cls.itau_bank_account = cls.res_partner_bank_model.create(
            {
                "acc_number": "205040",
                "bra_number": "1030",
                "bank_id": cls.bank_341.id,
                "company_id": cls.company.id,
                "partner_id": cls.company.partner_id.id,
            }
        )
        cls.bank_journal_itau = cls.env["account.journal"].create(
            {
                "name": "Itau Bank",
                "type": "bank",
                "code": "BNK_ITAU",
                "bank_account_id": cls.itau_bank_account.id,
                "bank_id": cls.bank_341.id,
            }
        )

        cls.bb_bank_account = cls.res_partner_bank_model.create(
            {
                "acc_number": "12345",
                "bra_number": "1234",
                "bank_id": cls.bank_001.id,
                "company_id": cls.company.id,
                "partner_id": cls.company.partner_id.id,
            }
        )
        cls.bank_journal_bb = cls.env["account.journal"].create(
            {
                "name": "BB Bank",
                "type": "bank",
                "code": "BNK_BB",
                "bank_account_id": cls.bb_bank_account.id,
                "bank_id": cls.bank_001.id,
            }
        )

    @classmethod
    def _setup_payment_modes(cls):
        cls.pix_mode = cls.payment_mode_model.create(
            {
                "bank_account_link": "fixed",
                "name": "Pix Transfer",
                "company_id": cls.company.id,
                "payment_method_id": cls.outbound_payment_method.id,
                "payment_mode_domain": "pix_transfer",
                "payment_order_ok": True,
                "fixed_journal_id": cls.bank_journal_itau.id,
                "cnab_processor": "oca_processor",
                "cnab_structure_id": cls.cnab_structure_itau_240.id,
                "cnab_payment_way_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref(
                                "l10n_br_cnab_structure.cnab_itau_240_pay_way_45"
                            ).id
                        ],
                    )
                ],
            }
        )

        cls.pix_mode_bb = cls.payment_mode_model.create(
            {
                "bank_account_link": "fixed",
                "name": "Pix Transfer BB",
                "company_id": cls.company.id,
                "payment_method_id": cls.outbound_payment_method.id,
                "payment_mode_domain": "pix_transfer",
                "payment_order_ok": True,
                "fixed_journal_id": cls.bank_journal_bb.id,
                "cnab_processor": "oca_processor",
                "cnab_structure_id": cls.cnab_structure_bb_240.id,
                "cnab_payment_way_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref(
                                "l10n_br_cnab_structure.cnab_bb_240_pay_way_45"
                            ).id
                        ],
                    )
                ],
            }
        )

    @classmethod
    def _setup_pix_data(cls):
        cls.res_partner_pix_model.create(
            {
                "partner_id": cls.partner_a.id,
                "key_type": "phone",
                "key": "+50372424737",
            }
        )

    @classmethod
    def _create_test_invoice(cls, payment_mode=None, amount=TEST_INVOICE_AMOUNT):
        return cls.env["account.move"].create(
            {
                "partner_id": cls.partner_a.id,
                "move_type": "in_invoice",
                "ref": "Test Invoice",
                "invoice_date": fields.Date.today(),
                "company_id": cls.company.id,
                "payment_mode_id": (payment_mode or cls.pix_mode).id,
                "journal_id": cls.company_data["default_journal_purchase"].id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product_a.id,
                            "quantity": 1.0,
                            "price_unit": amount,
                        },
                    )
                ],
            }
        )

    @classmethod
    def _create_payment_order(cls, invoice):
        invoice.action_post()
        cls.env["account.invoice.payment.line.multi"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create({}).run()

        domain = [
            ("state", "=", "draft"),
            ("payment_type", "=", "outbound"),
            ("company_id", "=", cls.company.id),
        ]
        return cls.payment_order_model.search(domain)

    def _create_cnab_structure(self, name="Test CNAB", bank=None, payment_method=None):
        bank = bank or self.bank_341
        payment_method = payment_method or self.env.ref(
            "l10n_br_account_payment_order.payment_mode_type_cnab240_out"
        )

        cnab_structure_form = Form(self.env["l10n_br_cnab.structure"])
        cnab_structure_form.name = name
        cnab_structure_form.bank_id = bank
        cnab_structure_form.payment_method_id = payment_method
        return cnab_structure_form.save()

    def _create_batch(self, cnab_structure, batch_name="Test Batch"):
        with Form(cnab_structure) as form:
            with form.batch_ids.new() as batch_form:
                batch_form.name = batch_name
        return cnab_structure.batch_ids[-1]

    def _create_line_with_field(
        self, cnab_structure, batch=None, line_type="header", **kwargs
    ):
        defaults = {
            "type": line_type,
            "communication_flow": "both",
            "start_pos": 1,
            "end_pos": 240,
        }
        defaults.update(kwargs)

        line_form = Form(
            self.env["l10n_br_cnab.line"],
            view="l10n_br_cnab_structure.cnab_line_form_view",
        )
        line_form.cnab_structure_id = cnab_structure

        line_form.batch_id = batch or line_form.batch_id

        line_form.communication_flow = defaults["communication_flow"]
        line_form.type = defaults["type"]

        extra_fields = {
            "segment": lambda form: setattr(
                form, "segment_code", kwargs.get("segment_code", "A")
            ),
        }
        extra_fields.get(line_type, lambda form: None)(line_form)

        with line_form.field_ids.new() as field_form:
            field_form.start_pos = defaults["start_pos"]
            field_form.end_pos = defaults["end_pos"]

        return line_form.save()

    def _create_valid_cnab_structure_complete(self):
        cnab_structure = self._create_cnab_structure()

        batch = self._create_batch(cnab_structure, "Batch 1")

        self._create_line_with_field(cnab_structure, line_type="header")
        self._create_line_with_field(cnab_structure, batch, line_type="header")
        self._create_line_with_field(
            cnab_structure, batch, line_type="segment", segment_code="X"
        )
        self._create_line_with_field(cnab_structure, batch, line_type="trailer")
        self._create_line_with_field(cnab_structure, line_type="trailer")

        return cnab_structure

    def _assert_cnab_240_defaults(self, cnab_structure):
        self.assertTrue(cnab_structure)
        self.assertRecordValues(
            cnab_structure,
            [
                {
                    "conf_bank_start_pos": POS_BANK_START,
                    "conf_bank_end_pos": POS_BANK_END,
                    "conf_record_type_start_pos": POS_REC_TYPE,
                    "conf_record_type_end_pos": POS_REC_TYPE,
                    "conf_batch_start_pos": POS_BATCH_START,
                    "conf_batch_end_pos": POS_BATCH_END,
                    "conf_detail_start_pos": POS_DETAIL_START,
                    "conf_detail_end_pos": POS_DETAIL_END,
                    "conf_segment_start_pos": POS_SEGMENT_START,
                    "conf_segment_end_pos": POS_SEGMENT_END,
                    "record_type_file_header_id": REC_FILE_HEADER,
                    "record_type_file_trailer_id": REC_FILE_TRAILER,
                    "record_type_batch_header_id": REC_BATCH_HEADER,
                    "record_type_batch_trailer_id": REC_BATCH_TRAILER,
                    "record_type_detail_id": REC_DETAIL,
                }
            ],
        )
        for outbound in cnab_structure.filtered(lambda s: s.payment_type == "outbound"):
            self.assertRecordValues(
                outbound,
                [
                    {
                        "conf_payment_way_start_pos": POS_WAY_START,
                        "conf_payment_way_end_pos": POS_WAY_END,
                    }
                ],
            )

    def test_file_generete_and_return(self):
        invoice = self._create_test_invoice()
        payment_order = self._create_payment_order(invoice)
        self.assertEqual(len(payment_order), 1)

        payment_order.draft2open()
        action = payment_order.open2generated()
        delivery_cnab_file = self.attachment_model.browse(action["res_id"])
        self.assertIsNotNone(delivery_cnab_file)

        cnab_data = base64.b64decode(delivery_cnab_file.datas).decode()
        lines = cnab_data.splitlines()

        lines[2] = replace_chars(lines[2], 154, "10112022")
        lines[2] = replace_chars(lines[2], 172, "300")
        lines[2] = replace_chars(lines[2], 230, "00")

        return_data = "\r\n".join(lines).encode()

        import_wizard = self.env["cnab.import.wizard"].create(
            {
                "journal_id": self.bank_journal_itau.id,
                "return_file": base64.b64encode(return_data),
                "filename": "TEST.RET",
                "type": "outbound",
                "cnab_structure_id": self.cnab_structure_itau_240.id,
            }
        )
        action = import_wizard.with_context(default_type="outbound").import_cnab()
        cnab_log = self.env["l10n_br_cnab.return.log"].browse(action["res_id"])

        self.assertIsNotNone(cnab_log)
        self.assertFalse(cnab_log.event_ids.mapped("generated_move_id"))

        cnab_log.action_confirm_return_log()
        self.assertTrue(cnab_log.event_ids.mapped("generated_move_id"))

    def test_cnab_yaml_output(self):
        invoice = self._create_test_invoice()
        payment_order = self._create_payment_order(invoice)

        preview_wizard = self.env["cnab.preview.wizard"].create(
            {
                "payment_order_id": payment_order.id,
                "cnab_structure_id": self.cnab_structure_itau_240.id,
            }
        )

        self.assertIsNotNone(preview_wizard.output_yaml)
        bank_name = unidecode(self.bank_341.name).upper()[:30].ljust(30)
        self.assertIn(
            f"    103_132_nome_do_banco: '{bank_name}'\n",
            preview_wizard.output_yaml,
        )

    def test_file_generate_bb_seq_detail_with_temp_files(self):
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            invoice_bb = self._create_test_invoice(
                payment_mode=self.pix_mode_bb, amount=150.0
            )
            payment_order = self._create_payment_order(invoice_bb)
            self.assertEqual(len(payment_order), 1)

            cnab_structure = self.cnab_structure_bb_240

            cnab_structure.unique_seq_per_segment = False
            payment_order.draft2open()
            action_false = payment_order.open2generated()
            cnab_data_false = base64.b64decode(
                self.attachment_model.browse(action_false["res_id"]).datas
            ).decode()

            tmp_file_false = tmp_path / "bb_seq_false.rem"
            tmp_file_false.write_text(cnab_data_false)

            lines_false = cnab_data_false.splitlines()
            seqs_false = [line[8:13] for line in lines_false if line[7] == "3"]
            self.assertTrue(
                all(seq == seqs_false[0] for seq in seqs_false),
            )

            cnab_structure.unique_seq_per_segment = True
            action_true = payment_order.open2generated()
            cnab_data_true = base64.b64decode(
                self.attachment_model.browse(action_true["res_id"]).datas
            ).decode()

            tmp_file_true = tmp_path / "bb_seq_true.rem"
            tmp_file_true.write_text(cnab_data_true)

            lines_true = cnab_data_true.splitlines()
            seqs_true = [line[8:13] for line in lines_true if line[7] == "3"]
            self.assertEqual(seqs_true, sorted(seqs_true))
            self.assertEqual(len(seqs_true), len(set(seqs_true)))

    def test_cnab_structure_240_outbound(self):
        cnab_structure = self._create_cnab_structure(
            payment_method=self.env.ref(
                "l10n_br_account_payment_order.payment_mode_type_cnab240_out"
            )
        )
        self._assert_cnab_240_defaults(cnab_structure)

    def test_cnab_structure_240_inbound(self):
        cnab_structure = self._create_cnab_structure(
            payment_method=self.env.ref(
                "l10n_br_account_payment_order.payment_mode_type_cnab240"
            )
        )
        self.assertTrue(cnab_structure)
        self._assert_cnab_240_defaults(cnab_structure)

    def test_cnab_structure_400_inbound(self):
        cnab_structure = self._create_cnab_structure(
            payment_method=self.env.ref(
                "l10n_br_account_payment_order.payment_mode_type_cnab400"
            )
        )
        self.assertTrue(cnab_structure)
        self.assertEqual(cnab_structure.conf_record_type_start_pos, POS_REC_TYPE)
        self.assertEqual(cnab_structure.conf_record_type_end_pos, POS_REC_TYPE)
        self.assertEqual(cnab_structure.record_type_file_trailer_id, REC_FILE_TRAILER)
        self.assertEqual(cnab_structure.record_type_detail_id, 1)

    def test_cnab_structure_500_inbound(self):
        cnab_structure = self._create_cnab_structure(
            payment_method=self.env.ref(
                "l10n_br_account_payment_order.payment_mode_type_cnab500"
            )
        )
        self.assertEqual(cnab_structure.conf_record_type_start_pos, 0)

    def test_cnab_structure_states(self):
        cnab_structure = self._create_valid_cnab_structure_complete()

        self.assertEqual(cnab_structure.state, "draft")

        cnab_structure.action_review()
        self.assertEqual(cnab_structure.state, "review")

        cnab_structure.action_approve()
        self.assertEqual(cnab_structure.state, "approved")

        cnab_structure.action_draft()
        self.assertEqual(cnab_structure.state, "draft")

    def test_multiple_batch_headers(self):
        cnab_structure = self._create_cnab_structure(
            name="Test Multiple Headers", bank=self.bank_001
        )
        batch = self._create_batch(cnab_structure, "Batch 1")

        cnab_structure.line_ids.unlink()

        self._create_line_with_field(
            cnab_structure, line_type="header", name="File Header", sequence=1
        )
        self._create_line_with_field(
            cnab_structure, batch, line_type="header", name="Batch Header 1", sequence=2
        )
        self._create_line_with_field(
            cnab_structure, batch, line_type="header", name="Batch Header 2", sequence=3
        )
        self._create_line_with_field(
            cnab_structure, batch, line_type="segment", name="Segment A", sequence=4
        )
        self._create_line_with_field(
            cnab_structure, batch, line_type="trailer", name="Batch Trailer", sequence=5
        )
        self._create_line_with_field(
            cnab_structure, line_type="trailer", name="File Trailer", sequence=6
        )

        batch.check_batch()

        header_lines = batch.line_ids.filtered(lambda line: line.type == "header")
        self.assertEqual(len(header_lines), 2)

    def test_payment_rules(self):
        cnab_structure = self.cnab_structure_itau_240

        if not cnab_structure.batch_ids:
            self._create_batch(cnab_structure, "Batch 1")
        batch = cnab_structure.batch_ids[0]

        way_same_bank = self.env["cnab.payment.way"].create(
            {
                "code": PAY_WAY_SAME_BANK,
                "description": "Credit Same Bank",
                "cnab_structure_id": cnab_structure.id,
                "batch_id": batch.id,
            }
        )
        way_other_bank = self.env["cnab.payment.way"].create(
            {
                "code": PAY_WAY_OTHER_BANK,
                "description": "TED Other Bank",
                "cnab_structure_id": cnab_structure.id,
                "batch_id": batch.id,
            }
        )

        self.env["l10n_br_cnab.payment.rule"].create(
            {
                "cnab_structure_id": cnab_structure.id,
                "sequence": 10,
                "match_bank_type": "same",
                "match_partner_type": "any",
                "payment_way_id": way_same_bank.id,
                "service_type": SVC_SUPPLIER,
            }
        )
        self.env["l10n_br_cnab.payment.rule"].create(
            {
                "cnab_structure_id": cnab_structure.id,
                "sequence": 20,
                "match_bank_type": "other",
                "match_partner_type": "any",
                "payment_way_id": way_other_bank.id,
                "service_type": SVC_SALARY,
            }
        )

        invoice = self._create_test_invoice()
        payment_order = self._create_payment_order(invoice)

        line_same = self.env["account.payment.line"].create(
            {
                "order_id": payment_order.id,
                "partner_id": self.partner_a.id,
                "partner_bank_id": self.partner_a_itau_bank.id,
                "amount_currency": 100.0,
            }
        )
        line_same._compute_cnab_payment_way_id()
        self.assertEqual(line_same.cnab_payment_way_id, way_same_bank)
        self.assertEqual(line_same.service_type, SVC_SUPPLIER)

        invoice_2 = self._create_test_invoice()
        payment_order_2 = self._create_payment_order(invoice_2)

        line_other = self.env["account.payment.line"].create(
            {
                "order_id": payment_order_2.id,
                "partner_id": self.partner_a.id,
                "partner_bank_id": self.partner_a_bb_bank.id,
                "amount_currency": 200.0,
            }
        )
        line_other._compute_cnab_payment_way_id()
        self.assertEqual(line_other.cnab_payment_way_id, way_other_bank)
        self.assertEqual(line_other.service_type, SVC_SALARY)

        with self.subTest("_compute_cnab_beneficiary_name"):
            self.partner_a_itau_bank.acc_holder_name = "São Paulo"
            line_same._compute_cnab_beneficiary_name()
            self.assertEqual(
                line_same.cnab_beneficiary_name,
                unidecode("São Paulo").strip(),
            )
            self.partner_a_itau_bank.acc_holder_name = False
            line_other._compute_cnab_beneficiary_name()
            self.assertEqual(
                line_other.cnab_beneficiary_name,
                unidecode(self.partner_a.name).strip(),
            )

    def test_unique_sequence_per_segment_behavior(self):
        cnab_structure = self.cnab_structure_bb_240

        invoice_1 = self._create_test_invoice()
        payment_order = self._create_payment_order(invoice_1)

        invoice_2 = self._create_test_invoice(amount=200.0)
        invoice_2.action_post()
        self.env["account.invoice.payment.line.multi"].with_context(
            active_model="account.move", active_ids=invoice_2.ids
        ).create({}).run()

        payment_order.draft2open()

        cnab_structure.unique_seq_per_segment = False
        action_false = payment_order.open2generated()
        data_false = (
            base64.b64decode(self.attachment_model.browse(action_false["res_id"]).datas)
            .decode()
            .splitlines()
        )
        details_false = [line[8:13] for line in data_false if line[7] == "3"]

        self.assertEqual(details_false[0], details_false[1])
        self.assertNotEqual(details_false[0], details_false[2])

        cnab_structure.unique_seq_per_segment = True
        payment_order.state = "open"
        action_true = payment_order.open2generated()
        data_true = (
            base64.b64decode(self.attachment_model.browse(action_true["res_id"]).datas)
            .decode()
            .splitlines()
        )
        details_true = [line[8:13] for line in data_true if line[7] == "3"]

        self.assertEqual(details_true[0], details_true[1])
        self.assertNotEqual(details_true[0], details_true[2])
        self.assertEqual(int(details_true[2]), int(details_true[0]) + 1)

    def test_batch_grouping_by_service_type(self):
        cnab_structure = self.cnab_structure_itau_240

        batch = cnab_structure.batch_ids[:1] or self._create_batch(
            cnab_structure, "Default Batch"
        )

        way_ted = self.env["cnab.payment.way"].create(
            {
                "code": PAY_WAY_OTHER_BANK,
                "description": "TED",
                "cnab_structure_id": cnab_structure.id,
                "batch_id": batch.id,
            }
        )
        way_cc = self.env["cnab.payment.way"].create(
            {
                "code": PAY_WAY_SAME_BANK,
                "description": "Current Account",
                "cnab_structure_id": cnab_structure.id,
                "batch_id": batch.id,
            }
        )

        test_mode = self.env["account.payment.mode"].create(
            {
                "name": "Test Grouping Mode",
                "bank_account_link": "fixed",
                "company_id": self.company.id,
                "payment_method_id": self.outbound_payment_method.id,
                "fixed_journal_id": self.bank_journal_itau.id,
                "cnab_structure_id": cnab_structure.id,
                "cnab_payment_way_ids": [(6, 0, [way_ted.id, way_cc.id])],
                "cnab_processor": "oca_processor",
            }
        )

        payment_order = self.env["account.payment.order"].create(
            {
                "payment_mode_id": test_mode.id,
                "state": "draft",
                "company_id": self.company.id,
                "journal_id": self.bank_journal_itau.id,
            }
        )

        # The service type is computed from the rules (it is no longer taken
        # from the vals): supplier -> TED/20, employee -> current account/30.
        rule_model = self.env["l10n_br_cnab.payment.rule"]
        rule_model.create(
            {
                "cnab_structure_id": cnab_structure.id,
                "sequence": 10,
                "match_bank_type": "any",
                "match_partner_type": "employee",
                "payment_way_id": way_cc.id,
                "service_type": SVC_SALARY,
            }
        )
        rule_model.create(
            {
                "cnab_structure_id": cnab_structure.id,
                "sequence": 20,
                "match_bank_type": "any",
                "match_partner_type": "supplier",
                "payment_way_id": way_ted.id,
                "service_type": SVC_SUPPLIER,
            }
        )
        employee_partner = self.partner_b
        employee_partner.employee = True
        employee_bank = self._create_partner_bank(
            self.bank_341, partner_id=employee_partner.id
        )

        line_supplier = self.env["account.payment.line"].create(
            {
                "order_id": payment_order.id,
                "partner_id": self.partner_a.id,
                "partner_bank_id": self.partner_a_itau_bank.id,
                "amount_currency": 100.0,
                "communication": "TEST BATCH 1",
            }
        )
        line_employee = self.env["account.payment.line"].create(
            {
                "order_id": payment_order.id,
                "partner_id": employee_partner.id,
                "partner_bank_id": employee_bank.id,
                "amount_currency": 200.0,
                "communication": "TEST BATCH 2",
            }
        )
        self.assertEqual(line_supplier.service_type, SVC_SUPPLIER)
        self.assertEqual(line_employee.service_type, SVC_SALARY)

        payment_order._compute_cnab_processor()
        payment_order._compute_cnab_structure_id()

        payment_order.draft2open()
        action = payment_order.open2generated()

        cnab_file = self.attachment_model.browse(action["res_id"])
        cnab_content = base64.b64decode(cnab_file.datas).decode()
        lines = cnab_content.splitlines()

        batch_headers = [line for line in lines if len(line) > 8 and line[7] == "1"]

        self.assertEqual(
            len(batch_headers),
            2,
        )

        found_types = [h[9:11] for h in batch_headers]
        self.assertIn(SVC_SUPPLIER, found_types)
        self.assertIn(SVC_SALARY, found_types)

    def test_field_select_wizard(self):
        cnab_structure = self._create_valid_cnab_structure_complete()
        cnab_field_id = cnab_structure.line_ids[0].field_ids[0]

        wiz_action = cnab_field_id.action_change_field_sending()

        self.assertEqual(wiz_action["res_model"], "field.select.wizard")
        self.assertEqual(wiz_action["target"], "new")
        self.assertEqual(wiz_action["type"], "ir.actions.act_window")
        self.assertEqual(wiz_action["view_mode"], "form")
        self.assertEqual(wiz_action["view_type"], "form")

        field_select_wizard = (
            self.env[wiz_action["res_model"]]
            .with_context(**wiz_action["context"])
            .create({})
        )

        def find_field(name):
            model = field_select_wizard.parent_model_id
            field = self.env["ir.model.fields"].search(
                [("model_id", "=", model.id), ("name", "=", name)]
            )
            return field

        self.assertFalse(field_select_wizard.notation_field)
        field_select_wizard.new_field_id = find_field("company_partner_bank_id")
        field_select_wizard._update_dot_notation()
        self.assertEqual(field_select_wizard.notation_field, "company_partner_bank_id")

        field_select_wizard.new_field_id = find_field("bank_id")
        field_select_wizard._update_dot_notation()
        self.assertEqual(
            field_select_wizard.notation_field, "company_partner_bank_id.bank_id"
        )

        field_select_wizard.action_remove_last_field()
        self.assertEqual(field_select_wizard.notation_field, "company_partner_bank_id")

        self.assertFalse(cnab_field_id.content_source_field)
        field_select_wizard.action_confirm()
        self.assertEqual(cnab_field_id.content_source_field, "company_partner_bank_id")

    # ------------------------------------------------------------------
    # Itau SISPAG segment A (salary): same bank group and strict validation
    # ------------------------------------------------------------------
    def _create_itau_salary_rules(self):
        cnab_structure = self.cnab_structure_itau_240
        self.way_01 = self.env.ref("l10n_br_cnab_structure.cnab_itau_240_pay_way_01")
        self.way_41 = self.env.ref("l10n_br_cnab_structure.cnab_itau_240_pay_way_41")
        rule_model = self.env["l10n_br_cnab.payment.rule"]
        rule_model.create(
            {
                "cnab_structure_id": cnab_structure.id,
                "sequence": 10,
                "match_bank_type": "same",
                "match_partner_type": "any",
                "payment_way_id": self.way_01.id,
                "service_type": SVC_SALARY,
            }
        )
        rule_model.create(
            {
                "cnab_structure_id": cnab_structure.id,
                "sequence": 20,
                "match_bank_type": "other",
                "match_partner_type": "any",
                "payment_way_id": self.way_41.id,
                "service_type": SVC_SALARY,
            }
        )

    def _create_itau_salary_mode(self):
        return self.env["account.payment.mode"].create(
            {
                "name": "Itau Salary Mode",
                "bank_account_link": "fixed",
                "company_id": self.company.id,
                "payment_method_id": self.outbound_payment_method.id,
                "fixed_journal_id": self.bank_journal_itau.id,
                "cnab_structure_id": self.cnab_structure_itau_240.id,
                "cnab_payment_way_ids": [(6, 0, [self.way_01.id, self.way_41.id])],
                "cnab_processor": "oca_processor",
            }
        )

    def _create_itau_salary_line(self, partner_bank, way):
        mode = self._create_itau_salary_mode()
        order = self.payment_order_model.create(
            {
                "payment_mode_id": mode.id,
                "state": "draft",
                "company_id": self.company.id,
                "journal_id": self.bank_journal_itau.id,
            }
        )
        line = self.payment_line_model.create(
            {
                "order_id": order.id,
                "partner_id": self.partner_a.id,
                "partner_bank_id": partner_bank.id,
                "amount_currency": 100.0,
                "service_type": SVC_SALARY,
                "cnab_payment_way_id": way.id,
                "communication": "SALARY TEST",
            }
        )
        return order, line

    def _generate_segment_a(self, order):
        order.draft2open()
        action = order.open2generated()
        data = base64.b64decode(self.attachment_model.browse(action["res_id"]).datas)
        lines = data.decode().splitlines()
        batch_headers = [x for x in lines if len(x) > 8 and x[7] == "1"]
        segments = [x for x in lines if len(x) > 13 and x[7] == "3" and x[13] == "A"]
        self.assertEqual(len(segments), 1)
        return batch_headers, segments[0]

    def _create_partner_bank(self, bank, **vals):
        values = {
            "bank_id": bank.id,
            "partner_id": self.env["res.partner"].create({"name": "Bank Holder"}).id,
            "acc_number": "123456",
            "bra_number": "1234",
            "acc_number_dig": "7",
        }
        values.update(vals)
        return self.res_partner_bank_model.create(values)

    def test_itau_salary_same_bank_segment_a(self):
        """Group 1 (same bank) must fill branch, account and DAC."""
        self._create_itau_salary_rules()
        partner_bank = self._create_partner_bank(self.bank_341)
        order, _line = self._create_itau_salary_line(partner_bank, self.way_01)
        batch_headers, seg = self._generate_segment_a(order)
        self.assertEqual(batch_headers[0][9:11], SVC_SALARY)
        self.assertEqual(seg[20:23], "341")
        self.assertEqual(seg[23], "0")
        self.assertEqual(seg[24:28], "1234")
        self.assertEqual(seg[28], " ")
        self.assertEqual(seg[29:35], "000000")
        self.assertEqual(seg[35:41], "123456")
        self.assertEqual(seg[41], " ")
        self.assertEqual(seg[42], "7")

    def test_itau_salary_other_bank_segment_a(self):
        """Group 2 (other banks) layout is unchanged; format only."""
        self._create_itau_salary_rules()
        partner_bank = self._create_partner_bank(
            self.bank_001, acc_number="789012", bra_number="2", acc_number_dig="X"
        )
        order, _line = self._create_itau_salary_line(partner_bank, self.way_41)
        batch_headers, seg = self._generate_segment_a(order)
        self.assertEqual(batch_headers[0][9:11], SVC_SALARY)
        self.assertEqual(seg[20:23], "001")
        self.assertEqual(seg[23:28], "00002")
        self.assertEqual(seg[28], " ")
        self.assertEqual(seg[29:41], "000000789012")
        self.assertEqual(seg[41], " ")
        self.assertEqual(seg[42], "X")

    def _strict_field(self, suffix):
        return self.env.ref(
            "l10n_br_cnab_structure.cnab_itau_240_pagamentos_segmento_a_" + suffix
        )

    def _assert_strict_error(self, field, line, *fragments):
        with self.assertRaises(UserError) as ctx:
            field.output(line, strict=True)
        message = str(ctx.exception)
        for fragment in fragments:
            self.assertIn(fragment, message)
        return message

    def test_itau_strict_validation(self):
        self._create_itau_salary_rules()
        field_branch = self._strict_field("25_28b")
        field_account = self._strict_field("36_41b")
        field_dac = self._strict_field("43_43b")
        for field in (field_branch, field_account, field_dac):
            self.assertTrue(field.raise_on_overflow)
        partner_bank = self._create_partner_bank(self.bank_341)
        _order, line = self._create_itau_salary_line(partner_bank, self.way_01)

        # Valid values
        self.assertEqual(field_branch.output(line, strict=True)[1], "1234")
        self.assertEqual(field_account.output(line, strict=True)[1], "123456")
        self.assertEqual(field_dac.output(line, strict=True)[1], "7")

        # Account with embedded check digit and separator
        partner_bank.acc_number = "12345-6"
        message = self._assert_strict_error(
            field_account, line, "12345-6", self.partner_a.name, "36", "41"
        )
        self.assertNotIn(TEST_PARTNER_CNPJ, message)
        # Account with 7 significant digits (embedded DAC, no separator)
        partner_bank.acc_number = "1234567"
        self._assert_strict_error(field_account, line, "1234567")
        # Leading zeros do not count against the limit
        partner_bank.acc_number = "0012345"
        self.assertEqual(field_account.output(line, strict=True)[1], "012345")
        # Shorter values are zero filled
        partner_bank.acc_number = "123"
        self.assertEqual(field_account.output(line, strict=True)[1], "000123")
        # Empty account
        partner_bank.acc_number = False
        self._assert_strict_error(field_account, line)
        partner_bank.acc_number = "123456"

        # Empty branch
        partner_bank.bra_number = False
        self._assert_strict_error(field_branch, line)
        partner_bank.bra_number = "1234"

        # DAC: empty, letter and two digits
        for dac in (False, "A", "12"):
            partner_bank.acc_number_dig = dac
            self._assert_strict_error(field_dac, line)

        # Legacy branch with 5 digits (the ORM constraint blocks it)
        partner_bank.acc_number_dig = "7"
        with self.assertRaises(UserError):
            partner_bank.bra_number = "12345"
        self.env.cr.execute(
            "UPDATE res_partner_bank SET bra_number = %s WHERE id = %s",
            ("12345", partner_bank.id),
        )
        partner_bank.invalidate_recordset()
        self._assert_strict_error(field_branch, line, "12345")

        # Without strict the behaviour is unchanged (silent truncation)
        self.assertEqual(field_branch.output(line)[1], "1234")

    def test_itau_strict_validation_not_applied_to_other_fields(self):
        """Fields without the flag keep the legacy behaviour."""
        self._create_itau_salary_rules()
        field_other = self._strict_field("30_41")
        self.assertFalse(field_other.raise_on_overflow)
        partner_bank = self._create_partner_bank(
            self.bank_001, acc_number="12345-6789012345"
        )
        _order, line = self._create_itau_salary_line(partner_bank, self.way_41)
        self.assertEqual(field_other.output(line, strict=True)[1], "123456789012")

    def test_format_leading_zeros_only_with_strict_flag(self):
        """Stripping leading zeros is Itau strict only; other fields unchanged."""
        field_strict = self._strict_field("36_41b")
        self.assertTrue(field_strict.raise_on_overflow)
        field_other = self._strict_field("30_41")
        self.assertFalse(field_other.raise_on_overflow)
        self.assertEqual(field_strict.format(6, "num", "0012345"), "012345")
        # Legacy behaviour for fields without the flag: plain truncation
        self.assertEqual(field_other.format(6, "num", "0012345"), "001234")
        self.assertEqual(field_other.format(6, "num", "123"), "000123")

    def test_itau_strict_preview_does_not_raise(self):
        """The CNAB line form preview must never raise on invalid data."""
        self._create_itau_salary_rules()
        partner_bank = self._create_partner_bank(self.bank_341, acc_number="12345-6")
        _order, line = self._create_itau_salary_line(partner_bank, self.way_01)
        field_account = self._strict_field("36_41b")
        field_account.cnab_line_id.resource_ref = f"account.payment.line,{line.id}"
        field_account.invalidate_recordset(["preview_field"])
        self.assertTrue(field_account.preview_field)
        # Same for a field of another bank layout
        other_field = self.env.ref(
            "l10n_br_cnab_structure.cnab_bb_240_pagamentos_segmento_a_24_28"
        )
        other_field.cnab_line_id.resource_ref = f"account.payment.line,{line.id}"
        other_field.invalidate_recordset(["preview_field"])
        self.assertTrue(other_field.preview_field)

    # ------------------------------------------------------------------
    # Service type reproduction (real flow: invoice -> payment line multi)
    # ------------------------------------------------------------------
    def _create_employee_rule(self):
        way_45 = self.env.ref("l10n_br_cnab_structure.cnab_itau_240_pay_way_45")
        return self.env["l10n_br_cnab.payment.rule"].create(
            {
                "cnab_structure_id": self.cnab_structure_itau_240.id,
                "sequence": 5,
                "match_bank_type": "any",
                "match_partner_type": "employee",
                "payment_way_id": way_45.id,
                "service_type": SVC_SALARY,
            }
        )

    def test_service_type_supplier_without_rule(self):
        """PAY0005 reproduction: supplier PIX, no rule at all.

        Cause (i) + vals: with no rule the compute is not involved and the
        "20" comes from _prepare_payment_line_vals (in_invoice default),
        confirmed by this test. PAY0005 was not a salary. Passes before and
        after the fix.
        """
        self.assertFalse(self.cnab_structure_itau_240.cnab_payment_rule_ids)
        invoice = self._create_test_invoice()
        order = self._create_payment_order(invoice)
        line = order.payment_line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.service_type, SVC_SUPPLIER)
        self.assertEqual(
            line.cnab_payment_way_id,
            self.env.ref("l10n_br_cnab_structure.cnab_itau_240_pay_way_45"),
        )

    def test_service_type_salary_with_employee_rule(self):
        """Employee flag + active "employee" rule must give service type 30.

        Cause (ii): before the fix this test FAILS, because the "20" passed
        in the vals by _prepare_payment_line_vals prevails: the surviving
        _compute_cnab_payment_way_id has no @api.depends, so it never runs
        on create and the stored value is the one from the vals.
        """
        self._create_employee_rule()
        self.partner_a.employee = True
        invoice = self._create_test_invoice()
        order = self._create_payment_order(invoice)
        line = order.payment_line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.service_type, SVC_SALARY)
        self.assertEqual(
            line.cnab_payment_way_id,
            self.env.ref("l10n_br_cnab_structure.cnab_itau_240_pay_way_45"),
        )

    # ------------------------------------------------------------------
    # Same bank by code, employee flag, exported orders, order computes
    # ------------------------------------------------------------------
    def test_same_bank_by_code_with_duplicated_bank(self):
        """Two res.bank records with code 341 must still be the "same bank"."""
        duplicated = self.env["res.bank"].create(
            {"name": "Itau duplicated", "code_bc": "341"}
        )
        self.assertNotEqual(duplicated, self.bank_341)
        payee_bank = self._create_partner_bank(duplicated)
        _order, line = self._create_itau_salary_line_for_rules(payee_bank)
        self.assertEqual(line.order_id.journal_id.bank_id, self.bank_341)
        self.assertEqual(line._get_cnab_bank_type(), "same")
        self.assertEqual(line._get_matching_rule().payment_way_id, self.way_01)
        # 409 (Unibanco) is treated as 341
        duplicated.code_bc = "409"
        line.invalidate_recordset()
        self.assertEqual(line._get_cnab_bank_type(), "same")
        # Different code or empty code is "other"
        duplicated.code_bc = "001"
        self.assertEqual(line._get_cnab_bank_type(), "other")
        duplicated.code_bc = False
        self.assertEqual(line._get_cnab_bank_type(), "other")

    def _create_itau_salary_line_for_rules(self, partner_bank):
        self._create_itau_salary_rules()
        return self._create_itau_salary_line(partner_bank, self.way_01)

    def test_employee_by_flag(self):
        """Only the res.partner.employee flag is used by the base module."""
        partner_bank = self._create_partner_bank(self.bank_341)
        _order, line = self._create_itau_salary_line_for_rules(partner_bank)
        self.assertFalse(self.partner_a.employee)
        self.assertFalse(line._is_cnab_employee())
        self.partner_a.employee = True
        self.assertTrue(line._is_cnab_employee())

    def test_employee_rule_matches_by_flag(self):
        rule = self._create_employee_rule()
        self.partner_a.employee = True
        invoice = self._create_test_invoice()
        order = self._create_payment_order(invoice)
        line = order.payment_line_ids
        self.assertEqual(line._get_matching_rule(), rule)
        self.partner_a.employee = False
        self.assertFalse(line._get_matching_rule())

    def test_exported_order_keeps_service_type(self):
        """Recompute never rewrites service type of an exported order."""
        self._create_employee_rule()
        self.partner_a.employee = True
        invoice = self._create_test_invoice()
        order = self._create_payment_order(invoice)
        line = order.payment_line_ids
        self.assertEqual(line.service_type, SVC_SALARY)
        order.draft2open()
        order.open2generated()
        self.assertEqual(order.state, "generated")
        # flag change: recompute leaves the stored service type alone
        self.partner_a.employee = False
        line._compute_cnab_payment_way_id()
        self.assertEqual(line.service_type, SVC_SALARY)
        # bank code change: same
        self.bank_341.code_bc = "237"
        line._compute_cnab_payment_way_id()
        self.assertEqual(line.service_type, SVC_SALARY)
        self.bank_341.code_bc = "341"
        # payment way is frozen too, and no UserError is raised even when no
        # way/rule matches any more
        way = line.cnab_payment_way_id
        self.assertTrue(way)
        mode_ways = order.payment_mode_id.cnab_payment_way_ids
        order.payment_mode_id.cnab_payment_way_ids = False
        order.payment_mode_id.cnab_structure_ok = True
        line._compute_cnab_payment_way_id()
        self.assertEqual(line.cnab_payment_way_id, way)
        self.assertEqual(line.service_type, SVC_SALARY)
        # in a draft order the recompute does apply
        order.payment_mode_id.cnab_payment_way_ids = mode_ways
        order.state = "draft"
        line._compute_cnab_payment_way_id()
        self.assertEqual(line.service_type, SVC_SUPPLIER)

    def test_exported_legacy_line_without_stored_way(self):
        """Upgrade case: exported line with service type but no stored way."""
        self._create_employee_rule()
        self.partner_a.employee = True
        invoice = self._create_test_invoice()
        order = self._create_payment_order(invoice)
        line = order.payment_line_ids
        way = line.cnab_payment_way_id
        order.draft2open()
        order.open2generated()
        self.env.cr.execute(
            "UPDATE account_payment_line SET cnab_payment_way_id = NULL WHERE id = %s",
            (line.id,),
        )
        line.invalidate_recordset()
        line._compute_cnab_payment_way_id()
        self.assertEqual(line.cnab_payment_way_id, way)
        self.assertEqual(line.service_type, SVC_SALARY)

    def test_order_computes_handle_multiple_records(self):
        """The computes must fill every record, not only the first one."""
        invoice_1 = self._create_test_invoice()
        order_1 = self._create_payment_order(invoice_1)
        order_2 = self.payment_order_model.create(
            {
                "payment_mode_id": self.pix_mode_bb.id,
                "state": "draft",
                "company_id": self.company.id,
                "journal_id": self.bank_journal_bb.id,
            }
        )
        orders = order_1 | order_2
        orders._compute_cnab_processor()
        orders._compute_cnab_structure_id()
        self.assertEqual(order_1.cnab_structure_id, self.cnab_structure_itau_240)
        self.assertEqual(order_2.cnab_structure_id, self.cnab_structure_bb_240)
        self.assertEqual(order_1.cnab_processor, "oca_processor")
        self.assertEqual(order_2.cnab_processor, "oca_processor")

    # ------------------------------------------------------------------
    # PIX key verbatim formatting, PIX segment A and match_pix_key criterion
    # ------------------------------------------------------------------
    PIX_KEYS = {
        "phone": "+5511987654321",
        "email": "fin@fornecedor.com.br",
        "cnpj_cpf": "12345678909",
        "evp": "123e4567-e89b-12d3-a456-426614174000",
    }
    PIX_CODES = {"phone": "01", "email": "02", "cnpj_cpf": "03", "evp": "04"}

    def test_pix_key_field_is_verbatim(self):
        """The Itau PIX key field keeps the exact key, left-aligned and padded."""
        field = self.env.ref(
            "l10n_br_cnab_structure.cnab_itau_240_pagamentos_segmento_b_128_227"
        )
        self.assertEqual(field.type, "raw")
        self.assertEqual(field.content_source_field, "partner_pix_id.key")
        for key in (*self.PIX_KEYS.values(), "ABC-Def@X.com"):
            result = field.format(field.size, field.type, key)
            self.assertEqual(result, key.ljust(field.size))
            self.assertEqual(len(result), field.size)

    def test_pix_key_field_raw_keeps_uppercase_evp(self):
        """Documents current behaviour: raw does not change the case of the key."""
        field = self.env.ref(
            "l10n_br_cnab_structure.cnab_itau_240_pagamentos_segmento_b_128_227"
        )
        evp = "123E4567-E89B-12D3-A456-426614174000"
        self.assertEqual(field.format(field.size, "raw", evp), evp.ljust(field.size))

    def test_alpha_field_format_unchanged(self):
        """Regular alphanumeric fields still strip symbols and uppercase."""
        field = self.env.ref(
            "l10n_br_cnab_structure.cnab_itau_240_pagamentos_segmento_b_15_16"
        )
        self.assertEqual(field.type, "alpha")
        self.assertEqual(
            field.format(30, "alpha", "fin@fornecedor.com.br"),
            "FINFORNECEDORCOMBR".ljust(30),
        )

    def test_pix_key_other_banks_unchanged(self):
        """Santander stays alpha (separate PR); BB and Sicoob are untouched."""
        santander = self.env.ref(
            "l10n_br_cnab_structure.cnab_santander_240_pagamentos_segmento_b_128_226"
        )
        self.assertEqual(santander.type, "alpha")
        raws = self.env["l10n_br_cnab.line.field"].search([("type", "=", "raw")])
        self.assertEqual(
            raws,
            self.env.ref(
                "l10n_br_cnab_structure.cnab_itau_240_pagamentos_segmento_b_128_227"
            ),
        )

    def _create_pix_key(self, key_type, key):
        return self.res_partner_pix_model.create(
            {"partner_id": self.partner_a.id, "key_type": key_type, "key": key}
        )

    def _create_salary_order(self):
        mode = self._create_itau_salary_mode()
        return self.payment_order_model.create(
            {
                "payment_mode_id": mode.id,
                "state": "draft",
                "company_id": self.company.id,
                "journal_id": self.bank_journal_itau.id,
            }
        )

    def _add_salary_line(self, order, partner_bank, pix_key=None):
        vals = {
            "order_id": order.id,
            "partner_id": self.partner_a.id,
            "partner_bank_id": partner_bank.id,
            "amount_currency": 100.0,
            "communication": "SALARY TEST",
        }
        if pix_key:
            vals["partner_pix_id"] = pix_key.id
        return self.payment_line_model.create(vals)

    def _create_salary_line_by_rule(self, partner_bank, pix_key=None):
        """Employee line on a non-PIX mode: way and service come from rules."""
        order = self._create_salary_order()
        return order, self._add_salary_line(order, partner_bank, pix_key)

    def _create_pix_employee_rules(self, same_bank_first=True, with_key=True):
        """Employee rules; all use the service type decided for employees."""
        self._create_itau_salary_rules()
        self.env["l10n_br_cnab.payment.rule"].search(
            [("cnab_structure_id", "=", self.cnab_structure_itau_240.id)]
        ).unlink()
        self.way_45 = self.env.ref("l10n_br_cnab_structure.cnab_itau_240_pay_way_45")
        rule_model = self.env["l10n_br_cnab.payment.rule"]

        def rule(sequence, bank, pix, way):
            rule_model.create(
                {
                    "cnab_structure_id": self.cnab_structure_itau_240.id,
                    "sequence": sequence,
                    "match_bank_type": bank,
                    "match_partner_type": "any",
                    "match_pix_key": pix,
                    "payment_way_id": way.id,
                    "service_type": SVC_EMPLOYEE,
                }
            )

        if same_bank_first:
            rule(1, "same", "any", self.way_01)
            if with_key:
                rule(2, "any", "with_key", self.way_45)
        else:
            if with_key:
                rule(1, "any", "with_key", self.way_45)
            rule(2, "same", "any", self.way_01)
        rule(3, "any", "any", self.way_41)

    def _generate_cnab_lines(self, order):
        order.draft2open()
        action = order.open2generated()
        data = base64.b64decode(self.attachment_model.browse(action["res_id"]).datas)
        return data.decode().splitlines()

    @staticmethod
    def _segments(lines, segment):
        return [x for x in lines if len(x) > 13 and x[7] == "3" and x[13] == segment]

    def test_rule_match_pix_key_default_is_any(self):
        """Existing rules keep the old behaviour: any PIX key condition."""
        self._create_itau_salary_rules()
        rules = self.env["l10n_br_cnab.payment.rule"].search(
            [("cnab_structure_id", "=", self.cnab_structure_itau_240.id)]
        )
        self.assertTrue(rules)
        self.assertEqual(set(rules.mapped("match_pix_key")), {"any"})
        pix = self._create_pix_key("email", self.PIX_KEYS["email"])
        same = self._create_partner_bank(self.bank_341)
        _order, line = self._create_salary_line_by_rule(same, pix)
        self.assertEqual(line._get_matching_rule().payment_way_id, self.way_01)
        _order, line = self._create_salary_line_by_rule(same)
        self.assertEqual(line._get_matching_rule().payment_way_id, self.way_01)

    def test_rule_match_pix_key_with_and_without(self):
        """with_key only matches lines with a key; without_key the opposite."""
        self._create_pix_employee_rules(same_bank_first=False)
        rule_model = self.env["l10n_br_cnab.payment.rule"]
        rule_model.search([("match_pix_key", "=", "any")]).filtered(
            lambda r: r.match_bank_type == "any"
        ).write({"match_pix_key": "without_key"})
        pix = self._create_pix_key("email", self.PIX_KEYS["email"])
        other = self._create_partner_bank(self.bank_001)
        _order, line = self._create_salary_line_by_rule(other, pix)
        self.assertEqual(line.cnab_payment_way_id, self.way_45)
        _order, line = self._create_salary_line_by_rule(other)
        self.assertEqual(line.cnab_payment_way_id, self.way_41)
        self.assertEqual(line._get_matching_rule().match_pix_key, "without_key")

    def test_rule_precedence_same_bank_first(self):
        """Same bank before with_key: Itau account stays on way 01 even with key."""
        self._create_pix_employee_rules(same_bank_first=True)
        pix = self._create_pix_key("email", self.PIX_KEYS["email"])
        same = self._create_partner_bank(self.bank_341)
        other = self._create_partner_bank(self.bank_001)
        _order, line = self._create_salary_line_by_rule(same, pix)
        self.assertEqual(line.cnab_payment_way_id, self.way_01)
        self.assertEqual(line.service_type, SVC_EMPLOYEE)
        _order, line = self._create_salary_line_by_rule(other, pix)
        self.assertEqual(line.cnab_payment_way_id, self.way_45)
        self.assertEqual(line.service_type, SVC_EMPLOYEE)
        _order, line = self._create_salary_line_by_rule(other)
        self.assertEqual(line.cnab_payment_way_id, self.way_41)

    def test_rule_precedence_key_first(self):
        """Inverse order proves that sequence decides the winner."""
        self._create_pix_employee_rules(same_bank_first=False)
        pix = self._create_pix_key("email", self.PIX_KEYS["email"])
        same = self._create_partner_bank(self.bank_341)
        _order, line = self._create_salary_line_by_rule(same, pix)
        self.assertEqual(line.cnab_payment_way_id, self.way_45)
        _order, line = self._create_salary_line_by_rule(same)
        self.assertEqual(line.cnab_payment_way_id, self.way_01)

    def test_rule_line_created_before_key_does_not_match_with_key(self):
        """partner_pix_id is stored once on the line: no key then no with_key."""
        self._create_pix_employee_rules(same_bank_first=False)
        other = self._create_partner_bank(self.bank_001)
        _order, line = self._create_salary_line_by_rule(other)
        self._create_pix_key("email", self.PIX_KEYS["email"])
        line.invalidate_recordset()
        self.assertFalse(line.partner_pix_id)
        self.assertEqual(line.cnab_payment_way_id, self.way_41)

    def test_pix_way_fills_pix_types_on_non_pix_mode(self):
        """A PIX way chosen by rule fills key type and transfer type."""
        self._create_pix_employee_rules(same_bank_first=False)
        pix = self._create_pix_key("email", self.PIX_KEYS["email"])
        other = self._create_partner_bank(self.bank_001)
        order, line = self._create_salary_line_by_rule(other, pix)
        self.assertNotEqual(order.payment_mode_id.payment_mode_domain, "pix_transfer")
        self.assertEqual(line.cnab_pix_type_id.code, "02")
        self.assertEqual(line.cnab_pix_transfer_type_id.code, "04")
        _order, line = self._create_salary_line_by_rule(other)
        self.assertFalse(line.cnab_pix_transfer_type_id)

    def test_itau_pix_keys_segment_a_b_all_types(self):
        """PIX salary: seg. A 113-114 = 04; seg. B key intact; per-line key type."""
        self._create_pix_employee_rules(same_bank_first=False)
        other = self._create_partner_bank(self.bank_001)
        order = self._create_salary_order()
        keys = list(self.PIX_KEYS.items())
        for key_type, key in keys:
            self._add_salary_line(order, other, self._create_pix_key(key_type, key))
        for line, (key_type, _key) in zip(order.payment_line_ids, keys, strict=True):
            self.assertEqual(line.cnab_pix_type_id.code, self.PIX_CODES[key_type])
        lines = self._generate_cnab_lines(order)
        header = [x for x in lines if len(x) > 8 and x[7] == "1"][0]
        self.assertEqual(header[9:11], SVC_EMPLOYEE)
        self.assertEqual(header[11:13], "45")
        seg_a = self._segments(lines, "A")
        seg_b = self._segments(lines, "B")
        self.assertEqual(len(seg_a), len(keys))
        self.assertEqual(len(seg_b), len(keys))
        for a_rec in seg_a:
            self.assertEqual(a_rec[112:114], "04")
        for b_rec, (key_type, key) in zip(seg_b, keys, strict=True):
            self.assertEqual(b_rec[14:16], self.PIX_CODES[key_type])
            self.assertEqual(b_rec[127:227], key.ljust(100))

    def test_itau_salary_without_key_is_not_pix(self):
        """Employee without key leaves as TED (way 41), not as PIX key."""
        self._create_pix_employee_rules(same_bank_first=False)
        other = self._create_partner_bank(self.bank_001)
        order, _line = self._create_salary_line_by_rule(other)
        lines = self._generate_cnab_lines(order)
        header = [x for x in lines if len(x) > 8 and x[7] == "1"][0]
        self.assertEqual(header[11:13], "41")
        self.assertNotEqual(self._segments(lines, "A")[0][112:114], "04")

    def test_pix_key_without_type_mapping_blocks_generation(self):
        """A key whose type has no Itau mapping aborts the CNAB with the name."""
        self._create_pix_employee_rules(same_bank_first=False)
        self.env["cnab.pix.key.type"].search(
            [
                ("cnab_structure_id", "=", self.cnab_structure_itau_240.id),
                ("key_type", "=", "evp"),
            ]
        ).unlink()
        other = self._create_partner_bank(self.bank_001)
        order, line = self._create_salary_line_by_rule(
            other, self._create_pix_key("evp", self.PIX_KEYS["evp"])
        )
        self.assertFalse(line.cnab_pix_type_id)
        attachments_before = self.attachment_model.search_count([])
        order.draft2open()
        with self.assertRaises(UserError) as ctx:
            order.open2generated()
        self.assertIn(self.partner_a.name, str(ctx.exception))
        self.assertEqual(self.attachment_model.search_count([]), attachments_before)

    def test_pix_key_without_mapping_does_not_block_non_pix_line(self):
        """Only lines leaving as PIX key are blocked (narrow condition)."""
        self._create_pix_employee_rules(same_bank_first=True)
        self.env["cnab.pix.key.type"].search(
            [
                ("cnab_structure_id", "=", self.cnab_structure_itau_240.id),
                ("key_type", "=", "evp"),
            ]
        ).unlink()
        same = self._create_partner_bank(self.bank_341)
        order, line = self._create_salary_line_by_rule(
            same, self._create_pix_key("evp", self.PIX_KEYS["evp"])
        )
        self.assertEqual(line.cnab_payment_way_id, self.way_01)
        line._check_cnab_pix_key_type()

    def test_pix_way_without_key_blocks_generation(self):
        """A line on a PIX way (rule 'any') without a PIX key aborts the CNAB."""
        self._create_pix_employee_rules(same_bank_first=False)
        self.env["l10n_br_cnab.payment.rule"].search(
            [
                ("cnab_structure_id", "=", self.cnab_structure_itau_240.id),
                ("payment_way_id", "=", self.way_45.id),
            ]
        ).write({"match_pix_key": "any"})
        other = self._create_partner_bank(self.bank_001)
        order, line = self._create_salary_line_by_rule(other)
        self.assertEqual(line.cnab_payment_way_id, self.way_45)
        order.draft2open()
        with self.assertRaises(UserError) as ctx:
            order.open2generated()
        self.assertIn(self.partner_a.name, str(ctx.exception))

    def test_pix_transfer_mode_by_account_without_key_generates(self):
        """pix_transfer mode, Itau way 45, no key but transactional account."""
        partner_bank = self._create_partner_bank(
            self.bank_341, transactional_acc_type="checking"
        )
        order = self.payment_order_model.create(
            {
                "payment_mode_id": self.pix_mode.id,
                "state": "draft",
                "company_id": self.company.id,
                "journal_id": self.bank_journal_itau.id,
            }
        )
        line = self._add_salary_line(order, partner_bank)
        self.assertFalse(line.partner_pix_id)
        way_45 = self.env.ref("l10n_br_cnab_structure.cnab_itau_240_pay_way_45")
        self.assertEqual(line.cnab_payment_way_id, way_45)
        self.assertEqual(line.cnab_pix_transfer_type_id.code, "01")
        lines = self._generate_cnab_lines(order)
        self.assertEqual(self._segments(lines, "A")[0][112:114], "01")
