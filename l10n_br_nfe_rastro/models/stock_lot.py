# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    def _prepare_nfe40_rastro_vals(self, quantity):
        """Values of one NF-e traceability group (rastro) for this lot.

        The lot dates are datetimes stored in UTC; the NF-e expects the
        calendar date as seen by the user.
        """
        self.ensure_one()
        return {
            "nfe40_nLote": self.name,
            "nfe40_qLote": quantity,
            "nfe40_dFab": self._nfe40_rastro_date(self.production_date),
            "nfe40_dVal": self._nfe40_rastro_date(self.expiration_date),
        }

    def _nfe40_rastro_date(self, value):
        if not value:
            return False
        return fields.Datetime.context_timestamp(self, value).date()
