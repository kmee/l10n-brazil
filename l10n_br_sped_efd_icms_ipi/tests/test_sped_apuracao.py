# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from odoo.addons.l10n_br_tax_assessment.tests.common_entrada import SpedEntradaCommon

from .test_sped_entrada import EntradaHelpers


@tagged("post_install", "-at_install")
class TestSpedEfdIcmsIpiApuracao(EntradaHelpers, SpedEntradaCommon):
    """The entry in the books and in the ICMS assessment (E110)."""

    def _set_accountant(self):
        city = self.env["res.city"].search([("state_id.code", "=", "SP")], limit=1)
        self.company.accountant_id = self.env["res.partner"].create(
            {
                "name": "Accountant",
                "is_accountant": True,
                "cnpj_cpf": "111.444.777-35",
                "crc_code": "1SP123456/O-0",
                "phone": "11999999999",
                "email": "accountant@example.com",
                "country_id": self.env.ref("base.br").id,
                "state_id": self.env.ref("base.state_br_sp").id,
                "city_id": city.id,
            }
        )

    def _assess_icms_of_july(self):
        """The assessment by the normal path: compute from the ledger, post."""
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
        payable = self.env["account.account"].create(
            {
                "name": "ICMS a recolher",
                "code": "ICMSPAY",
                "account_type": "liability_current",
                "company_id": self.company.id,
            }
        )
        receivable = self.env["account.account"].create(
            {
                "name": "ICMS a recuperar",
                "code": "ICMSREC",
                "account_type": "asset_current",
                "company_id": self.company.id,
            }
        )
        group.with_company(self.company).write(
            {
                "property_tax_payable_account_id": payable.id,
                "property_tax_receivable_account_id": receivable.id,
            }
        )
        assessment = self.env["l10n_br_tax.assessment"].create(
            {
                "company_id": self.company.id,
                "tax_group_id": group.id,
                "date_from": "2026-07-01",
                "date_to": "2026-07-31",
            }
        )
        assessment.action_compute()
        assessment.action_post()
        return assessment

    def test_generation_stops_without_the_posted_icms_assessment(self):
        """No assessment, no E110, and the PVA refuses the file: the generation
        stops with a message that says what to do."""
        self._set_accountant()
        self._purchase_move("fo_compras_compras_comercializacao", "601")
        declaration = self._declaration_july()
        with self.assertRaises(UserError) as error:
            declaration.button_create_sped_files()
        self.assertIn("ICMS", error.exception.args[0])

    def test_the_entry_without_credit_carries_no_icms(self):
        """Use and consumption: the ICMS stays in the cost, the books carry CST
        of the origin plus 90 and no base, rate or value, in the C170, in the
        C190 and in the C100. The resale keeps its credit."""
        resale = self._purchase_move("fo_compras_compras_comercializacao", "602")
        consumption = self._purchase_move("fo_compras_compras_uso_consumo", "603")
        declaration = self._declaration_july()
        c100 = self._c100(declaration)
        by_number = {
            doc.document_number: c100[doc.document_number]
            for doc in (resale.fiscal_document_id, consumption.fiscal_document_id)
        }
        self.assertGreater(
            self._number(
                by_number[resale.fiscal_document_id.document_number]["VL_ICMS"]
            ),
            0,
        )
        self.assertEqual(
            self._number(
                by_number[consumption.fiscal_document_id.document_number]["VL_ICMS"]
            ),
            0.0,
        )
        c190 = {(rec["CFOP"]): rec for rec in self._sped_records(declaration, "C190")}
        credited = [r for r in c190.values() if self._number(r["VL_ICMS"]) > 0]
        not_credited = [r for r in c190.values() if self._number(r["VL_ICMS"]) == 0]
        self.assertTrue(credited and not_credited)
        for rec in not_credited:
            self.assertTrue(rec["CST_ICMS"].endswith("90"), rec)
            self.assertEqual(self._number(rec["VL_BC_ICMS"]), 0.0)
            self.assertGreater(self._number(rec["VL_OPR"]), 0)
        c170 = {rec["CFOP"]: rec for rec in self._sped_records(declaration, "C170")}
        for cfop, rec in c170.items():
            if cfop in c190 and c190[cfop] in not_credited:
                self.assertTrue(rec["CST_ICMS"].endswith("90"))
                self.assertEqual(self._number(rec["VL_ICMS"]), 0.0)

    def test_e110_credits_match_the_c190_of_the_entries(self):
        """The PVA crosses E110 field 5 with the ICMS of the entry C190: both
        come from what the company has the right to credit."""
        self._purchase_move("fo_compras_compras_comercializacao", "604")
        self._purchase_move("fo_compras_compras_uso_consumo", "605")
        self._assess_icms_of_july()
        declaration = self._declaration_july()
        c190_credit = sum(
            self._number(rec["VL_ICMS"])
            for rec in self._sped_records(declaration, "C190")
            if rec["CFOP"].startswith(("1", "2", "3"))
        )
        e110 = self._sped_records(declaration, "E110")
        self.assertEqual(len(e110), 1)
        self.assertEqual(self._number(e110[0]["VL_TOT_CREDITOS"]), c190_credit)
        self.assertGreater(c190_credit, 0)
        # and the file is generated (a company that is not an IPI taxpayer)
        self._set_accountant()
        declaration.IND_ATIV = "1"
        declaration.button_create_sped_files()
        self.assertTrue(declaration.message_ids)
