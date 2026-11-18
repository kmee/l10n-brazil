# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBillDivergenceTranslation(TransactionCase):
    """Every text of the divergence of the bill is in Portuguese on the screen:
    the badge, the filter, the labels of the line and the helps."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("pt_BR")
        cls.env["ir.module.module"]._load_module_terms(
            ["l10n_br_purchase_stock"], ["pt_BR"], overwrite=True
        )
        cls.env = cls.env(context=dict(cls.env.context, lang="pt_BR"))

    def _arch(self, xmlid, view_type):
        view = self.env.ref(xmlid)
        return self.env["account.move"].get_view(view.id, view_type)["arch"]

    def test_the_badge_of_the_bill(self):
        arch = self._arch("account.view_move_form", "form")
        self.assertIn("Divergente", arch)
        self.assertNotIn(">Divergent<", arch)
        self.assertIn("Alguma linha difere do pedido", arch)

    def test_the_filter_of_the_list_of_bills(self):
        arch = self._arch("account.view_account_invoice_filter", "search")
        self.assertIn("Divergente do pedido", arch)

    def test_the_labels_and_helps_of_the_fields(self):
        expected = {
            "account.move.line": {
                "purchase_ordered_qty": "Quantidade pedida",
                "purchase_received_qty": "Quantidade recebida",
                "purchase_price_unit": "Preço unitário do pedido",
                "purchase_qty_difference": "Diferença de quantidade",
                "purchase_price_difference": "Diferença de preço",
                "purchase_divergent": "Divergente",
            },
            "account.move": {"purchase_divergent": "Divergente"},
            "res.company": {
                "purchase_price_tolerance": "Tolerância de preço da fatura (%)",
                "purchase_quantity_tolerance": "Tolerância de quantidade da fatura (%)",
            },
        }
        for model, fields in expected.items():
            described = self.env[model].fields_get(list(fields), ["string", "help"])
            for name, label in fields.items():
                self.assertEqual(described[name]["string"], label, f"{model}.{name}")
                help_text = described[name]["help"]
                self.assertTrue(help_text, f"{model}.{name}")
                self.assertNotIn("differs", help_text, f"{model}.{name}")
