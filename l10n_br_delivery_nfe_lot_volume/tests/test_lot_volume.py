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
