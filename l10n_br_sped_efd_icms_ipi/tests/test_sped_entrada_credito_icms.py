# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

import logging
from datetime import date

from odoo.tests.common import tagged

from odoo.addons.l10n_br_tax_assessment.tests.common_entrada import SpedEntradaCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestSpedEntradaCreditoIcms(SpedEntradaCommon):
    """The ICMS credit of a purchase for use and consumption and of one for
    the fixed assets in the assessment (E110).

    Neither purchase gives the ICMS credit in the month of the entry: use and
    consumption has none (LC 87/1996, art. 33, I) and the fixed asset only the
    1/48 of the CIAP, which the localization does not run yet, so the ICMS of
    the asset stays in its cost. The vendor bill books no ICMS to recover and
    the E110 carries no credit for them. The C190 is not part of this: it
    still shows the ICMS of the document (120.00), and the test only records it.
    """

    def _purchase(self, operation_line, number):
        ref = self.env.ref
        move = self.init_invoice(
            "in_invoice",
            partner=self.partner_a,
            invoice_date=date(2026, 7, 10),
            products=[self.product_a],
            document_type=ref("l10n_br_fiscal.document_55"),
            fiscal_operation=ref("l10n_br_fiscal.fo_compras"),
            fiscal_operation_lines=[ref(f"l10n_br_fiscal.{operation_line}")],
            document_serie="1",
            document_number=number,
        )
        move.action_post()
        move.fiscal_document_id.write(
            {"state_edoc": "autorizada", "document_key": self._access_key(number)}
        )
        return move

    def _assessment_credit(self):
        group = self.env["account.tax.group"].search(
            [
                (
                    "fiscal_tax_group_id",
                    "=",
                    self.env.ref("l10n_br_fiscal.tax_group_icms").id,
                )
            ],
            limit=1,
        )
        self.assertTrue(group, "the chart loads an ICMS tax group")
        assessment = self.env["l10n_br_tax.assessment"].create(
            {
                "company_id": self.company.id,
                "tax_group_id": group.id,
                "date_from": "2026-07-01",
                "date_to": "2026-07-31",
            }
        )
        assessment.action_compute()
        credit = sum(
            assessment.line_ids.filtered(
                lambda line: line.kind == "credit" and line.source == "computed"
            ).mapped("tax_amount")
        )
        return credit, assessment

    def _books(self, move):
        declaration = self._declaration(
            "efd_icms_ipi", date(2026, 7, 1), date(2026, 7, 31)
        )
        c190 = self._sped_records(declaration, "C190")
        self.assertTrue(c190, "the C190 of the purchase is generated")
        return sum(float(rec["VL_ICMS"].replace(",", ".") or 0) for rec in c190)

    def _check(self, operation_line, number):
        move = self._purchase(operation_line, number)
        icms_lines = move.line_ids.filtered(
            lambda line: line.tax_line_id.tax_group_id.fiscal_tax_group_id.tax_domain
            == "icms"
        )
        self.assertFalse(icms_lines, "the vendor bill books no ICMS to recover")
        icms_in_c190 = self._books(move)
        _logger.info("%s C190 VL_ICMS: %.2f", operation_line, icms_in_c190)
        credit, assessment = self._assessment_credit()
        self.assertTrue(assessment, "the assessment is computed")
        self.assertAlmostEqual(credit, 0.0, msg=f"{operation_line} E110 credits")

    def test_use_and_consumption_purchase_credit(self):
        """No ICMS credit in the E110."""
        self._check("fo_compras_compras_uso_consumo", "201")

    def test_fixed_asset_purchase_credit(self):
        """No ICMS credit in the E110 until the CIAP exists: the ICMS of the
        asset stays in its cost, never the whole amount as a credit."""
        self._check("fo_compras_compras_ativo", "202")
