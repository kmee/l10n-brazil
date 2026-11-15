# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import importlib.util
import os

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase

M = "l10n_br_fiscal"


def _load_migration():
    path = os.path.join(
        get_module_path(M), "migrations", "16.0.26.4.0", "post-migration.py"
    )
    spec = importlib.util.spec_from_file_location("post_migration_26_4_0", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestIndustrializacaoReturnMigration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.remessa = cls.env.ref(f"{M}.fo_remessa_industrializacao")
        cls.entrada = cls.env.ref(f"{M}.fo_entrada_industrializacao")
        cls.entrada_retorno = cls.env.ref(f"{M}.fo_entrada_retorno_industrializacao")
        cls.retorno = cls.env.ref(f"{M}.fo_retorno_industrializacao")

    def test_new_installation_pairs_the_return_of_the_ordering_party(self):
        self.assertEqual(self.remessa.return_fiscal_operation_id, self.entrada_retorno)
        self.assertEqual(self.entrada.return_fiscal_operation_id, self.retorno)

    def test_migration_fixes_an_installed_database(self):
        """Bases installed before the fix still point to the manufacturer
        entry (1901) and the shipment (5901), noupdate data that -u skips."""
        self.remessa.return_fiscal_operation_id = self.entrada
        self.entrada.return_fiscal_operation_id = self.remessa
        _load_migration().fix_industrializacao_return(self.env)
        self.assertEqual(self.remessa.return_fiscal_operation_id, self.entrada_retorno)
        self.assertEqual(self.entrada.return_fiscal_operation_id, self.retorno)

    def test_migration_keeps_a_return_chosen_by_the_user(self):
        other = self.env.ref(f"{M}.fo_venda")
        self.remessa.return_fiscal_operation_id = other
        _load_migration().fix_industrializacao_return(self.env)
        self.assertEqual(self.remessa.return_fiscal_operation_id, other)
