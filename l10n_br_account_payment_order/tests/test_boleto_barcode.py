# Copyright (C) 2026 - KMEE (<http://kmee.com.br>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from .. import barcode_utils

# Synthetic (client data free) pairs: 44 digits barcode <-> 47 digits linha
# digitavel, with valid general DV (mod 11) and field DVs (mod 10).
PAIRS = [
    (
        "00193990100001234560123456789012345678901234",
        "00190123435678901234356789012343399010000123456",
    ),
    (
        "23798100000000009993456789012345678901234567",
        "23793456778901234567789012345677810000000000999",
    ),
    (
        "34193910000045678901090123456789012345678901",
        "34191090162345678901723456789017391000004567890",
    ),
]


@tagged("post_install", "-at_install")
class TestBoletoBarcodeUtils(TransactionCase):
    def test_digitable_line_to_barcode(self):
        for barcode, line in PAIRS:
            self.assertEqual(barcode_utils.barcode_from_digitable_line(line), barcode)
            self.assertEqual(barcode_utils.digitable_line_from_barcode(barcode), line)

    def test_dv_validation(self):
        for barcode, _line in PAIRS:
            self.assertTrue(barcode_utils.is_valid_barcode(barcode))
            # change one digit of the value: DV no longer matches
            bad = barcode[:10] + str((int(barcode[10]) + 1) % 10) + barcode[11:]
            self.assertFalse(barcode_utils.is_valid_barcode(bad))
        self.assertFalse(barcode_utils.is_valid_barcode("123"))
        self.assertFalse(barcode_utils.is_valid_barcode("A" * 44))

    def test_normalize_formats(self):
        barcode, line = PAIRS[0]
        formatted = (
            f"{line[0:5]}.{line[5:10]} {line[10:15]}.{line[15:21]} "
            f"{line[21:26]}.{line[26:32]} {line[32]} {line[33:]}"
        )
        for value in (line, formatted, barcode, f" {barcode[:20]}-{barcode[20:]} "):
            res = barcode_utils.normalize_barcode(value)
            self.assertEqual(res, (barcode, line, True), value)

    def test_normalize_invalid(self):
        barcode, line = PAIRS[0]
        bad_line = line[:-1] + str((int(line[-1]) + 1) % 10)
        self.assertEqual(
            barcode_utils.normalize_barcode(bad_line), (bad_line, False, False)
        )
        self.assertEqual(
            barcode_utils.normalize_barcode("1234"), ("1234", False, False)
        )
        self.assertEqual(barcode_utils.normalize_barcode(False), (False, False, False))

    def test_utility_48_digits(self):
        # Utility barcode built with mod 10 blocks (reference 6)
        core = "8" + "1" + "6" + "00000001234" + "5" * 29
        body = core[:3] + "0" + core[3:]
        dv = barcode_utils.mod10(body[:3] + body[4:])
        barcode = body[:3] + str(dv) + body[4:]
        self.assertTrue(barcode_utils.is_valid_barcode(barcode))
        line = "".join(
            block + str(barcode_utils.mod10(block))
            for block in (barcode[i : i + 11] for i in range(0, 44, 11))
        )
        self.assertEqual(len(line), 48)
        self.assertEqual(barcode_utils.normalize_barcode(line), (barcode, line, True))

    def test_utility_48_digits_mod11(self):
        # Utility barcode with mod 11 blocks (reference 8) and its 48 digit line
        body = "8" + "3" + "8" + "0" + "00000012345" + "6" * 29
        dv = barcode_utils.mod11_utility(body[:3] + body[4:])
        barcode = body[:3] + str(dv) + body[4:]
        self.assertTrue(barcode_utils.is_valid_barcode(barcode))
        line = barcode_utils.digitable_line_from_barcode(barcode)
        self.assertEqual(len(line), 48)
        self.assertEqual(
            line,
            "".join(
                block + str(barcode_utils.mod11_utility(block))
                for block in (barcode[i : i + 11] for i in range(0, 44, 11))
            ),
        )
        self.assertEqual(barcode_utils.barcode_from_digitable_line(line), barcode)
        self.assertEqual(
            barcode_utils.normalize_barcode(barcode), (barcode, line, True)
        )


@tagged("post_install", "-at_install")
class TestBoletoBarcodeLine(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        cls.chart_template = "br_oca_generic"
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.company_data["company"]
        cls.partner_a.vat = "45823449000198"
        method = cls.env.ref(
            "l10n_br_account_payment_order.payment_mode_type_cnab240_out"
        )
        cls.boleto_mode = cls.env["account.payment.mode"].create(
            {
                "bank_account_link": "variable",
                "name": "Boleto",
                "company_id": cls.company.id,
                "payment_method_id": method.id,
                "payment_mode_domain": "boleto",
                "payment_order_ok": True,
                "variable_journal_ids": cls.company_data["default_journal_bank"],
            }
        )
        cls.order = cls.env["account.payment.order"].create(
            {
                "payment_mode_id": cls.boleto_mode.id,
                "journal_id": cls.company_data["default_journal_bank"].id,
            }
        )

    def _line(self, **vals):
        values = {
            "order_id": self.order.id,
            "partner_id": self.partner_a.id,
            "amount_currency": 1234.56,
            "communication_type": "normal",
            "communication": "BOLETO TEST",
        }
        values.update(vals)
        return self.env["account.payment.line"].create(values)

    def test_create_converts_digitable_line(self):
        barcode, line = PAIRS[1]
        pline = self._line(barcode=line)
        self.assertEqual(pline.barcode, barcode)
        self.assertEqual(pline.digitable_line, line)

    def test_create_from_digitable_line_field(self):
        barcode, line = PAIRS[2]
        pline = self._line(digitable_line=line)
        self.assertEqual(pline.barcode, barcode)
        self.assertEqual(pline.digitable_line, line)

    def test_create_barcode_fills_digitable_line(self):
        barcode, line = PAIRS[0]
        pline = self._line(barcode=barcode)
        self.assertEqual(pline.barcode, barcode)
        self.assertEqual(pline.digitable_line, line)

    def test_write_normalizes(self):
        barcode, line = PAIRS[0]
        pline = self._line()
        pline.write({"barcode": f"{line[:5]}.{line[5:]}"})
        self.assertEqual(pline.barcode, barcode)
        self.assertEqual(pline.digitable_line, line)

    def test_invalid_is_kept_cleaned_and_blocks_confirmation(self):
        _barcode, line = PAIRS[0]
        bad = line[:-1] + str((int(line[-1]) + 1) % 10)
        pline = self._line(barcode=bad[:5] + "." + bad[5:])
        self.assertEqual(pline.barcode, bad)
        with self.assertRaises(UserError) as ctx:
            pline.draft2open_payment_line_check()
        message = str(ctx.exception)
        self.assertIn(pline.name, message)
        self.assertIn(self.partner_a.display_name, message)
        self.assertRegex(message, r"1[.,]234[.,]56")

    def test_missing_barcode_blocks_confirmation(self):
        pline = self._line()
        with self.assertRaises(UserError) as ctx:
            self.order.draft2open()
        self.assertIn(pline.name, str(ctx.exception))
        self.assertIn(self.partner_a.display_name, str(ctx.exception))

    def test_non_boleto_mode_is_not_blocked(self):
        ted = self.boleto_mode.copy({"name": "TED", "payment_mode_domain": "ted"})
        order = self.order.copy({"payment_mode_id": ted.id})
        pline = self._line(order_id=order.id)
        pline._check_boleto_barcode()  # no raise

    def test_legacy_47_digits_is_converted_on_check(self):
        barcode, line = PAIRS[1]
        pline = self._line()
        # simulate data stored before the normalization existed
        self.env.cr.execute(
            "UPDATE account_payment_line SET barcode=%s WHERE id=%s",
            (line, pline.id),
        )
        pline.invalidate_recordset()
        self.assertEqual(pline.barcode, line)
        pline.draft2open_payment_line_check()
        self.assertEqual(pline.barcode, barcode)
        self.assertEqual(pline.digitable_line, line)


@tagged("post_install", "-at_install")
class TestUtilityBlockDv(TransactionCase):
    def test_wrong_block_dv_is_invalid_not_recalculated(self):
        good = "826900000413526572026106260000123455678901234560"
        bad = good[:11] + str((int(good[11]) + 1) % 10) + good[12:]
        self.assertTrue(barcode_utils.normalize_barcode(good)[2])
        barcode, digitable_line, valid = barcode_utils.normalize_barcode(bad)
        self.assertFalse(valid)
        self.assertEqual(barcode, bad)
        self.assertFalse(digitable_line)
        self.assertTrue(barcode_utils.has_wrong_block_dv(bad))
        self.assertFalse(barcode_utils.has_wrong_block_dv(good))
