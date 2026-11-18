# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest import mock

from odoo import SUPERUSER_ID, api
from odoo.tests.common import TransactionCase, tagged

MIGRATION = (
    Path(__file__).parent.parent / "migrations" / "16.0.26.6.0" / "post-migration.py"
)


@tagged("post_install", "-at_install")
class TestMigrationSTDestination(TransactionCase):
    """An existing database gets the destination of the operation lines with
    ST, and keeps what the user chose."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # the migration decorator of openupgradelib hands the script an
        # environment: the test gives it the same, without the library
        def migrate(*args, **kwargs):
            def decorator(function):
                def wrapper(cr, version):
                    return function(api.Environment(cr, SUPERUSER_ID, {}), version)

                return wrapper

            return decorator

        openupgrade = ModuleType("openupgradelib.openupgrade")
        openupgrade.migrate = migrate
        library = ModuleType("openupgradelib")
        library.openupgrade = openupgrade
        spec = importlib.util.spec_from_file_location("migration_st", MIGRATION)
        cls.migration = importlib.util.module_from_spec(spec)
        with mock.patch.dict(
            sys.modules,
            {"openupgradelib": library, "openupgradelib.openupgrade": openupgrade},
        ):
            spec.loader.exec_module(cls.migration)
        cls.asset = cls.env.ref("l10n_br_fiscal.fo_compras_compras_ativost")
        cls.consumption = cls.env.ref("l10n_br_fiscal.fo_compras_compras_uso_consumost")

    def test_the_empty_destination_is_filled_and_the_choice_is_kept(self):
        # the database as it was before: noupdate data without destination
        self.asset.product_destination = False
        self.consumption.product_destination = "resale"
        self.migration.migrate(self.env.cr, "16.0.26.5.0")
        self.asset.invalidate_recordset()
        self.consumption.invalidate_recordset()
        self.assertEqual(self.asset.product_destination, "fixed_asset")
        self.assertEqual(self.consumption.product_destination, "resale")
        self.migration.migrate(self.env.cr, "16.0.26.5.0")
        self.assertEqual(self.asset.product_destination, "fixed_asset")
