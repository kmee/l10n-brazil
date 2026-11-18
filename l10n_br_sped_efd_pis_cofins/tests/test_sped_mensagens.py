# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from odoo.addons.l10n_br_tax_assessment.tests.common_entrada import SpedEntradaCommon

from .test_sped_credito import CreditMixin


@tagged("post_install", "-at_install")
class TestSpedPisCofinsMessages(CreditMixin, SpedEntradaCommon):
    """The messages that stop the generation are written for a fiscal user: the
    destination as the label of the selection and the values in the Brazilian
    format, not the raw value of the field or a decimal point."""

    profit_calculation = "real"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("pt_BR")
        cls.env["ir.module.module"]._load_module_terms(
            ["l10n_br_sped_efd_pis_cofins"], ["pt_BR"], overwrite=True
        )

    def test_the_stop_by_the_destination_says_the_item_and_what_to_do(self):
        """An old entry of use and consumption booked with CST 50 (before the
        entry CST followed the destination): the message says which note and
        item, why, and what to do, with the label of the destination."""
        bill = self._entry("fo_compras_compras_uso_consumo", "403")
        line = bill.fiscal_document_id.fiscal_line_ids
        line.entry_pis_cst_id = self.env.ref("l10n_br_fiscal.cst_pis_50")
        self._set_accountant()
        declaration = self._declaration_july()
        with self.assertRaises(UserError) as error:
            declaration.with_context(lang="pt_BR").button_create_sped_files()
        message = error.exception.args[0]
        self.assertIn("Uso e Consumo", message)
        self.assertNotIn("use_consumption", message)
        self.assertIn("item 1", message)
        self.assertIn(bill.fiscal_document_id.document_number, message)
        self.assertIn("trate esse crédito fora do sistema", message)

    def test_the_values_of_the_message_follow_the_brazilian_format(self):
        self._entry("fo_compras_compras_comercializacao", "401")
        self._assess("pis")
        self._assess("cofins")
        self._entry("fo_compras_compras", "402")
        self._set_accountant()
        declaration = self._declaration_july()
        with self.assertRaises(UserError) as error:
            declaration.with_context(lang="pt_BR").button_create_sped_files()
        message = error.exception.args[0]
        self.assertIn("33,00", message)
        self.assertIn("16,50", message)
        self.assertNotIn("33.00", message)
