# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

import base64
from datetime import date

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

    def test_generation_stops_without_an_accountant(self):
        self._purchase_move("fo_compras_compras_comercializacao", "606")
        declaration = self._declaration_july()
        self.company.accountant_id = False
        with self.assertRaises(UserError) as error:
            declaration.button_create_sped_files()
        self.assertIn("accountant", error.exception.args[0])

    def test_the_activity_and_the_classification_follow_the_company(self):
        """An IPI taxpayer is industrial with its classification; any other
        company is Outros, and the industrial one needs the IPI assessment."""
        self.assertEqual(self.company.industry_type, "00")
        declaration = self.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {
                "company_id": self.company.id,
                "DT_INI": "2026-07-01",
                "DT_FIN": "2026-07-31",
            }
        )
        self.assertEqual(declaration.IND_ATIV, "0")
        self.assertEqual(declaration.CLAS_ESTAB_IND, "00")
        self.company.write({"is_industry": False, "ripi": False})
        declaration._onchange_company_activity()
        self.assertEqual(declaration.IND_ATIV, "1")
        self.assertFalse(declaration.CLAS_ESTAB_IND)

    def test_an_industrial_declaration_needs_the_ipi_assessment(self):
        self._set_accountant()
        self._purchase_move("fo_compras_compras_comercializacao", "607")
        self._assess_icms_of_july()
        declaration = self._declaration_july()
        self.assertEqual(declaration.IND_ATIV, "0")
        with self.assertRaises(UserError) as error:
            declaration.button_create_sped_files()
        self.assertIn("IPI", error.exception.args[0])

    def _generated_text(self, declaration):
        attachment = self.env["ir.attachment"].search(
            [("res_model", "=", declaration._name), ("res_id", "=", declaration.id)],
            order="id desc",
            limit=1,
        )
        return base64.b64decode(attachment.datas).decode("latin-1")

    def test_the_file_has_the_registers_of_the_moment_of_the_generation(self):
        """The registers pulled before the assessment and the accountant are
        pulled again when the file is generated: no E110 or 0100 missing from a
        file made after the registration was fixed."""
        self._purchase_move("fo_compras_compras_comercializacao", "607")
        declaration = self._declaration_july()
        self.assertEqual(self._sped_records(declaration, "E110"), [])
        self._set_accountant()
        self._assess_icms_of_july()
        declaration.IND_ATIV = "1"
        declaration.button_create_sped_files()
        text = self._generated_text(declaration)
        self.assertIn("|E110|", text)
        self.assertIn("|0100|", text)

    def test_the_0100_stays_when_the_accountant_has_no_phone(self):
        """The phone is optional in the layout. The mapping broke on a missing
        one and the 0100 went out of the file with no word."""
        self._set_accountant()
        self.company.accountant_id.phone = False
        declaration = self._declaration_july()
        records = self._sped_records(declaration, "0100")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["FONE"], "")

    def test_generation_stops_with_what_the_accountant_lacks(self):
        """The mandatory fields of the 0100 (descriptor of the PVA) that the
        registration of the accountant does not have, said by name."""
        self._set_accountant()
        self.company.accountant_id.write({"email": False, "city_id": False})
        self._purchase_move("fo_compras_compras_comercializacao", "608")
        declaration = self._declaration_july()
        with self.assertRaises(UserError) as error:
            declaration.button_create_sped_files()
        self.assertIn("e-mail", error.exception.args[0])
        self.assertIn("city", error.exception.args[0])

    def test_generation_stops_when_an_earlier_month_was_never_assessed(self):
        """The same hole of the credit balance in the ICMS: June has movement and no
        assessment, so the balance that July starts from is not the real one."""
        self._purchase_move(
            "fo_compras_compras_comercializacao", "609", invoice_date=date(2026, 6, 10)
        )
        self._purchase_move("fo_compras_compras_comercializacao", "610")
        self._assess_icms_of_july()
        self._set_accountant()
        declaration = self._declaration_july()
        declaration.IND_ATIV = "1"
        with self.assertRaises(UserError) as error:
            declaration.button_create_sped_files()
        self.assertIn("06/2026", error.exception.args[0])
