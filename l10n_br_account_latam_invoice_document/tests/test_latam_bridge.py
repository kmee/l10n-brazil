# Copyright (C) 2026-Today - KMEE (<https://kmee.com.br>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged

BRIDGE = "odoo.addons.l10n_br_account_latam_invoice_document"


# loading a chart of accounts may install modules, which needs a loaded registry
@tagged("post_install", "-at_install")
class TestLatamBridge(TransactionCase):
    def test_brazilian_overrides_come_first(self):
        """The overrides of l10n_latam_invoice_document methods are the ones
        of this module, whatever the load order of l10n_br_account."""
        move_class = type(self.env["account.move"])
        for name in (
            "_check_l10n_latam_documents",
            "_compute_l10n_latam_document_type",
        ):
            method = getattr(move_class, name)
            self.assertTrue(method.__module__.startswith(BRIDGE), name)
        constraints = {
            method.__name__: method.__module__
            for method in self.env["account.move"]._constraint_methods
        }
        self.assertTrue(constraints["_check_l10n_latam_documents"].startswith(BRIDGE))

    def test_purchase_invoice_of_a_new_company_posts(self):
        """A company created after the installation, with the br_oca_generic
        chart, gets journals that use documents. Its purchase invoice posts
        without a manual document number and gets a document type."""
        template = self.env["account.chart.template"]._get_chart_template_mapping()
        module = template.get("br_oca_generic", {}).get("module")
        if not self.env["ir.module.module"].search_count(
            [("name", "=", module), ("state", "=", "installed")]
        ):
            self.skipTest("the br_oca_generic chart is not installed")
        company = self.env["res.company"].create(
            {"name": "Nova Empresa BR", "country_id": self.env.ref("base.br").id}
        )
        self.env.user.company_ids |= company
        self.env["account.chart.template"].try_loading(
            "br_oca_generic", company=company, install_demo=False
        )
        env = self.env(context=dict(self.env.context, allowed_company_ids=company.ids))
        journal = env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1
        )
        if not journal.l10n_latam_use_documents:
            self.skipTest("the purchase journal does not use documents here")
        partner = env["res.partner"].create({"name": "Fornecedor"})
        move = env["account.move"].create(
            {
                "move_type": "in_invoice",
                "company_id": company.id,
                "journal_id": journal.id,
                "partner_id": partner.id,
                "invoice_date": "2026-11-17",
                "invoice_line_ids": [
                    (0, 0, {"name": "Servico", "quantity": 1, "price_unit": 100.0})
                ],
            }
        )
        move.action_post()
        self.assertEqual(move.state, "posted")
        self.assertTrue(move.l10n_latam_document_type_id)
