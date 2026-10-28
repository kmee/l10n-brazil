# Copyright 2026 KMEE INFORMATICA LTDA - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockMove(models.Model):
    _inherit = "stock.move"

    duimp_item_id = fields.Many2one(
        comodel_name="l10n_br_duimp.item",
        string="DUIMP Item",
        copy=False,
        index="btree_not_null",
        ondelete="restrict",
        help="DUIMP item received by this move, confirmed by the user.",
    )

    @api.constrains("duimp_item_id", "product_id", "company_id")
    def _check_duimp_item(self):
        for move in self.filtered("duimp_item_id"):
            item = move.duimp_item_id
            if item.product_id != move.product_id:
                raise ValidationError(
                    _(
                        "The receipt of %(product)s cannot be linked to the DUIMP"
                        " item %(item)s, which is another product.",
                        product=move.product_id.display_name,
                        item=item.numero_item,
                    )
                )
            if item.company_id != move.company_id:
                raise ValidationError(
                    _("A receipt can only be linked to a DUIMP of its company.")
                )

    def _get_duimp_item_qty(self, item=None):
        """Quantity of this move in the unit of measure of the DUIMP item."""
        self.ensure_one()
        item = item or self.duimp_item_id
        product_uom = self.product_id.uom_id
        item_uom = item.uom_id or product_uom
        return product_uom._compute_quantity(self.product_qty, item_uom)

    def _get_duimp_customs_value(self):
        """Customs value of the DUIMP item, prorated to the quantity received.

        A DUIMP item received in more than one move (a backorder, for
        instance) weighs in each move only for the quantity it brought.
        """
        self.ensure_one()
        item = self.duimp_item_id
        if not item.quantidade:
            return 0.0
        return item.valor_aduaneiro * self._get_duimp_item_qty() / item.quantidade
