# Copyright 2024 Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import Command, fields
from odoo.tests.common import tagged

from odoo.addons.l10n_br_account.tests.common import AccountMoveBRCommon


@tagged("post_install", "-at_install")
class AccountMoveWithWhInvoice(AccountMoveBRCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env["account.chart.template"].load_fiscal_taxes(
            companies=[cls.company_data["company"]]
        )

        # Ensure the NFe user group is enabled so fiscal fields are available
        # on invoices when the l10n_br_nfe module is installed.
        nfe_user_group = cls.env.ref("l10n_br_nfe.group_user", raise_if_not_found=False)
        if nfe_user_group:
            cls.env.user.write({"groups_id": [Command.link(nfe_user_group.id)]})

        cls.configure_normal_company_taxes()
        # Only the withholding PIS/COFINS definitions must apply to the purchases
        cls.pis_tax_definition_empresa_lc.state = "expired"
        cls.cofins_tax_definition_empresa_lc.state = "expired"
        cls.pis_wh_tax_definition_empresa_lc.action_approve()
        cls.cofins_wh_tax_definition_empresa_lc.action_approve()

        cls.env.ref("l10n_br_fiscal.fo_compras").deductible_taxes = True
        cls.move_in_compra_para_revenda = cls.init_invoice(
            "in_invoice",
            products=[cls.product_a],
            document_type=cls.env.ref("l10n_br_fiscal.document_55"),
            fiscal_operation=cls.env.ref("l10n_br_fiscal.fo_compras"),
            fiscal_operation_lines=[
                cls.env.ref("l10n_br_fiscal.fo_compras_compras_comercializacao")
            ],
            document_serie="1",
            document_number="54",
        )
        cls.env.ref("l10n_br_fiscal.tax_group_pis_wh").generate_wh_invoice = True
        cls.env.ref("l10n_br_fiscal.tax_group_cofins_wh").generate_wh_invoice = True

        cls.service_test = cls.env["product.product"].create(
            {
                "name": "Serviço de Testes",
                "type": "service",
                "standard_price": 1000.0,
                "tax_icms_or_issqn": "issqn",
                "ncm_id": cls.env.ref("l10n_br_fiscal.ncm_00000000").id,
                "fiscal_type": "09",
                "fiscal_genre_id": cls.env.ref("l10n_br_fiscal.product_genre_00").id,
                "service_type_id": cls.env.ref("l10n_br_fiscal.service_type_1009").id,
                "taxes_id": False,
            }
        )

        cls.test_partner = cls.env["res.partner"].create(
            {
                "name": "Test Company Brasil",
                "legal_name": "Test Company Brasil Ltda",
                "vat": "32.680.221/0001-44",
                "state_id": cls.env.ref("base.state_br_sp").id,
                "city_id": cls.env.ref("l10n_br_base.city_3550308").id,
                "zip": "04576-060",
                "country_id": cls.env.ref("base.br").id,
                "l10n_br_ie_code": "621.240.850.633",
                "is_company": True,
                "active": True,
            }
        )
        cls.test_partner._onchange_city_id()

    @classmethod
    def setup_independent_company(cls, **kwargs):
        """Create a Lucro Presumido company, as in l10n_br_account tests."""
        company_name = kwargs.pop("name", "empresa 1 Lucro Presumido")
        cnpj = kwargs.pop("cnpj", "62.128.834/0001-34")
        kwargs.update(
            {
                "tax_framework": "3",
                "is_industry": True,
                "industry_type": "00",
                "profit_calculation": "presumed",
                "ripi": True,
                "piscofins_id": cls.env.ref(
                    "l10n_br_fiscal.tax_pis_cofins_columativo"
                ).id,
                "icms_regulation_id": cls.env.ref(
                    "l10n_br_fiscal.tax_icms_regulation"
                ).id,
                "cnae_main_id": cls.env.ref("l10n_br_fiscal.cnae_3101200").id,
                "document_type_id": cls.env.ref("l10n_br_fiscal.document_55").id,
                "country_id": cls.env.ref("base.br").id,
                "currency_id": cls.env.ref("base.BRL").id,
            }
        )
        company = super().setup_independent_company(**kwargs)
        company.name = company_name
        company.partner_id.state_id = cls.env.ref("base.state_br_sp").id
        company.partner_id.vat = cnpj
        return company

    def _check_wh_invoice_amounts(self, move):
        """Withholding invoices must carry the withheld amount (OCA #5003)."""
        for wh_line in move.wh_invoice_ids.invoice_line_ids:
            wh_invoice = wh_line.move_id
            amount = abs(wh_line.wh_move_line_id.balance)
            self.assertTrue(amount)
            self.assertEqual(wh_invoice.state, "posted")
            self.assertEqual(wh_invoice.amount_total, amount)
            self.assertEqual(wh_line.balance, amount)
            self.assertEqual(wh_line.amount_currency, amount)
            payable_line = wh_invoice.line_ids.filtered(
                lambda line: line.account_id.account_type == "liability_payable"
            )
            self.assertEqual(payable_line.balance, -amount)
            self.assertEqual(payable_line.amount_currency, -amount)

    def test_compra_para_revenda(self):
        """
        Test move with deductible taxes and withholding taxes: one withholding
        invoice is generated for each withheld tax (PIS and COFINS).
        """
        move = self.move_in_compra_para_revenda
        wh_tax_lines = move.line_ids.filtered(
            lambda line: (
                line.tax_line_id.tax_group_id.fiscal_tax_group_id.tax_withholding
            )
        )
        self.assertEqual(
            sorted(wh_tax_lines.mapped("tax_line_id.tax_group_id.fiscal_tax_group_id")),
            sorted(
                self.env.ref("l10n_br_fiscal.tax_group_pis_wh")
                | self.env.ref("l10n_br_fiscal.tax_group_cofins_wh")
            ),
        )
        # The tax accounts of the withheld taxes allow reconciliation
        wh_tax_lines.account_id.reconcile = True
        move.action_post()
        move._compute_wh_invoice_ids()
        self.assertEqual(
            move.wh_invoice_count,
            2,
            "The invoice should have 2 withholding invoices (PIS and COFINS).",
        )
        for wh_tax_line in wh_tax_lines:
            wh_line = move.wh_invoice_ids.invoice_line_ids.filtered(
                lambda line, wh_tax_line=wh_tax_line: line.wh_move_line_id
                == wh_tax_line
            )
            self.assertEqual(len(wh_line), 1)
            wh_invoice = wh_line.move_id
            fiscal_group = wh_tax_line.tax_line_id.tax_group_id.fiscal_tax_group_id
            amount = abs(wh_tax_line.balance)
            self.assertTrue(amount)
            self.assertEqual(wh_invoice.state, "posted")
            self.assertEqual(wh_invoice.move_type, "in_invoice")
            self.assertEqual(wh_invoice.partner_id, fiscal_group.partner_id)
            self.assertEqual(wh_invoice.invoice_origin, move.name)
            self.assertEqual(wh_invoice.amount_total, amount)
            self.assertEqual(wh_line.account_id, wh_tax_line.account_id)
            self.assertEqual(wh_line.balance, amount)
            self.assertEqual(wh_line.amount_currency, amount)
            payable_line = wh_invoice.line_ids.filtered(
                lambda line: line.account_id.account_type == "liability_payable"
            )
            self.assertEqual(payable_line.balance, -amount)
            self.assertEqual(payable_line.amount_currency, -amount)
            # The withheld tax line is reconciled with the withholding invoice
            self.assertTrue(wh_tax_line.reconciled)
            self.assertTrue(wh_line.reconciled)
            self.assertEqual(wh_tax_line.matched_debit_ids.debit_move_id, wh_line)

        # Back to draft cancels the withholding invoices and clears the link
        wh_invoices = move.wh_invoice_ids
        move.button_draft()
        self.assertEqual(set(wh_invoices.mapped("state")), {"cancel"})
        move._compute_wh_invoice_ids()
        self.assertEqual(move.wh_invoice_count, 0)
        self.assertFalse(wh_tax_lines.filtered("reconciled"))

    def test_with_partner_issqn_without_city_partner(self):
        "Test move with Partner defined and no ISSQN City Partner"
        self.env.ref("l10n_br_fiscal.tax_group_pis_wh").generate_wh_invoice = False
        self.env.ref("l10n_br_fiscal.tax_group_cofins_wh").generate_wh_invoice = False
        product = self.service_test
        tax_group = self.env.ref("l10n_br_fiscal.tax_group_issqn_wh")
        tax_group.generate_wh_invoice = True
        tax_group.journal_id = self.company_data["default_journal_purchase"].id
        move_issqn = self.init_invoice(
            "in_invoice",
            products=[product],
            partner=self.test_partner,
            document_type=self.env.ref("l10n_br_fiscal.document_55"),
            fiscal_operation=self.env.ref("l10n_br_fiscal.fo_compras"),
            fiscal_operation_lines=[self.env.ref("l10n_br_fiscal.fo_compras_servico")],
            document_serie="1",
            document_number="56",
        )

        for line_ids in move_issqn.invoice_line_ids:
            line_ids.issqn_tax_id = None
            line_ids.issqn_fg_city_id = self.env.ref("l10n_br_base.city_3550308")
            line_ids.issqn_wh_tax_id = self.env.ref("l10n_br_fiscal.tax_issqn_wh_5")

        move_issqn.action_post()
        move_issqn._compute_wh_invoice_ids()

        self.assertEqual(
            move_issqn.wh_invoice_count,
            1,
            "The invoice should have 1 withholding invoice (ISSQN).",
        )

        partner_wh = self.env["res.partner"].search(
            [
                ("city_id", "=", move_issqn.invoice_line_ids[0].issqn_fg_city_id.id),
                ("wh_cityhall", "=", True),
            ],
            limit=1,
        )

        expected_partner_id = partner_wh if partner_wh else tax_group.partner_id

        self.assertTrue(
            all(
                wh_inv.partner_id == expected_partner_id
                for wh_inv in move_issqn.wh_invoice_ids
            )
        )
        self._check_wh_invoice_amounts(move_issqn)

    def test_with_partner_issqn_with_city_partner(self):
        "Test move with Partner and ISSQN City Partner"
        self.env.ref("l10n_br_fiscal.tax_group_pis_wh").generate_wh_invoice = False
        self.env.ref("l10n_br_fiscal.tax_group_cofins_wh").generate_wh_invoice = False
        product = self.service_test
        wh_payable_account = self.env["account.account"].create(
            {
                "name": "Withholding Payable",
                "code": "WHT210",
                "account_type": "liability_payable",
                "reconcile": True,
                "company_ids": [Command.set(self.company_data["company"].ids)],
            }
        )

        tax_group = self.env.ref("l10n_br_fiscal.tax_group_issqn_wh")
        tax_group.write(
            {
                "generate_wh_invoice": True,
                "journal_id": self.company_data["default_journal_purchase"].id,
                "wh_payable_account_id": wh_payable_account.id,
            }
        )
        partner_cityhall = self.env["res.partner"].create(
            {
                "name": "Prefeitura de São Paulo",
                "city_id": self.env.ref("l10n_br_base.city_3550308").id,
                "state_id": self.env.ref("base.state_br_sp").id,
                "country_id": self.env.ref("base.br").id,
                "wh_cityhall": True,
            }
        )
        move_issqn = self.init_invoice(
            "in_invoice",
            products=[product],
            partner=partner_cityhall,
            document_type=self.env.ref("l10n_br_fiscal.document_55"),
            fiscal_operation=self.env.ref("l10n_br_fiscal.fo_compras"),
            fiscal_operation_lines=[self.env.ref("l10n_br_fiscal.fo_compras_servico")],
            document_serie="1",
            document_number="56",
        )

        for line_ids in move_issqn.invoice_line_ids:
            line_ids.issqn_tax_id = None
            line_ids.issqn_fg_city_id = self.env.ref("l10n_br_base.city_3550308")
            line_ids.issqn_wh_tax_id = self.env.ref("l10n_br_fiscal.tax_issqn_wh_5")

        move_issqn.action_post()
        move_issqn._compute_wh_invoice_ids()

        self.assertEqual(
            move_issqn.wh_invoice_count,
            1,
            "The invoice should have 1 withholding invoice (ISSQN).",
        )
        self.assertTrue(
            all(
                wh_inv.partner_id == partner_cityhall
                for wh_inv in move_issqn.wh_invoice_ids
            )
        )
        self._check_wh_invoice_amounts(move_issqn)
        payable_line_ids = move_issqn.wh_invoice_ids.line_ids.filtered(
            lambda line: line.account_id.account_type == "liability_payable"
        )
        self.assertTrue(
            all(
                pay_line.account_id == wh_payable_account
                for pay_line in payable_line_ids
            )
        )
        self._check_wh_invoice_amounts(move_issqn)

    def test_wh_due_date_day_beyond_month_end(self):
        """The due day is clamped to the last day of the month (no ValueError)."""
        move = self.move_in_compra_para_revenda
        move.action_post()
        wh_line = move.wh_invoice_ids.invoice_line_ids.wh_move_line_id[:1]
        self.assertTrue(wh_line, "A withholding invoice line is expected.")
        fiscal_group = wh_line.tax_line_id.tax_group_id.fiscal_tax_group_id
        # Without the fix, February.replace(day=31) raised ValueError.
        self.env.cr.execute(
            "UPDATE account_move SET date = %s WHERE id = %s",
            (fields.Date.to_date("2026-02-10"), move.id),
        )
        move.invalidate_recordset(["date"])
        fiscal_group.wh_due_day = 31
        vals = move._prepare_wh_invoice(wh_line, fiscal_group)
        self.assertEqual(vals["invoice_date_due"], fields.Date.to_date("2026-03-31"))
        fiscal_group.wh_due_day = 30
        self.env.cr.execute(
            "UPDATE account_move SET date = %s WHERE id = %s",
            (fields.Date.to_date("2026-01-20"), move.id),
        )
        move.invalidate_recordset(["date"])
        vals = move._prepare_wh_invoice(wh_line, fiscal_group)
        self.assertEqual(vals["invoice_date_due"], fields.Date.to_date("2026-02-28"))
