# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestLotVolume(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.picking = cls.env.ref(
            "l10n_br_delivery_nfe_lot_volume.picking_remessa_prateleiras"
        )
        cls.move = cls.env.ref(
            "l10n_br_delivery_nfe_lot_volume.move_remessa_prateleiras"
        )
        cls.line_1 = cls.env.ref(
            "l10n_br_delivery_nfe_lot_volume.move_line_remessa_prateleiras_1"
        )
        cls.line_2 = cls.env.ref(
            "l10n_br_delivery_nfe_lot_volume.move_line_remessa_prateleiras_2"
        )
        cls.volume = cls.env.ref(
            "l10n_br_delivery_nfe_lot_volume.volume_remessa_prateleiras_1"
        )

    def test_create_volume_with_lot(self):
        wizard = (
            self.env["stock.picking.vol.create"]
            .with_context(
                default_picking_id=self.picking.id, default_move_id=self.move.id
            )
            .create({})
        )
        self.assertEqual(wizard.line_ids.move_line_id, self.line_2)
        self.assertTrue(wizard.line_ids.selected)
        wizard.write({"quantity": "3", "gross_weight": 40})
        action = wizard.action_create_volume()
        volume = self.env["stock.picking.vol"].browse(action["res_id"])
        self.assertEqual(self.line_2.volume_id, volume)
        self.assertEqual(self.move.volume_ids, self.volume | volume)
        self.assertEqual(self.picking.number_of_volumes, 8)

    def test_add_lot_to_existing_volume(self):
        wizard = (
            self.env["stock.picking.vol.add"]
            .with_context(default_picking_id=self.picking.id)
            .create({"volume_id": self.volume.id})
        )
        wizard.line_ids.selected = True
        wizard.action_add_to_volume()
        self.assertEqual(self.volume.move_line_ids, self.line_1 | self.line_2)

    def test_validation_lock(self):
        picking_type = self.picking.picking_type_id
        picking_type.require_lot_volume = True
        with self.assertRaises(UserError):
            self.picking.button_validate()
        self.line_2.volume_id = self.volume
        self.assertFalse(self.picking._get_lines_without_volume())

    def test_validate_with_all_lots_in_volume(self):
        self.picking.picking_type_id.require_lot_volume = True
        self.line_2.volume_id = self.volume
        self.picking.with_context(
            skip_immediate=True, skip_backorder=True
        ).button_validate()
        self.assertFalse(self.picking._get_lines_without_volume())

    def test_open_wizards_and_remove_from_volume(self):
        action = self.move.action_open_create_volume_wizard()
        self.assertEqual(action["context"]["default_move_id"], self.move.id)
        self.assertEqual(action["context"]["default_picking_id"], self.picking.id)
        action = self.volume.action_open_add_lines_wizard()
        self.assertEqual(action["context"]["default_volume_id"], self.volume.id)
        self.line_1.action_remove_from_volume()
        self.assertFalse(self.line_1.volume_id)
        self.assertNotIn(self.volume, self.move.volume_ids)

    def test_display_name_with_and_without_lot(self):
        self.assertIn(f"[{self.line_1.lot_id.name}]", self.line_1.display_name)
        self.line_1.lot_id = False
        self.assertEqual(self.line_1.display_name, self.line_1.product_id.display_name)

    def test_volume_name_and_picking_totals(self):
        self.volume.write(
            {"nfe40_esp": "Caixa", "nfe40_marca": "KMEE", "nfe40_nVol": "7"}
        )
        self.assertEqual(self.volume.name, "Caixa/KMEE/7")
        self.volume.write({"nfe40_esp": False, "nfe40_marca": False})
        self.assertEqual(self.volume.name, "//7")
        new = self.env["stock.picking.vol"].create(
            {"picking_id": self.picking.id, "nfe40_qVol": "2"}
        )
        self.assertTrue(self.picking.has_vol)
        self.assertEqual(new.picking_id, self.picking)
