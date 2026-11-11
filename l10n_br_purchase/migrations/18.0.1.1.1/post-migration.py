# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Recompute stored totals of draft/sent POs in a foreign currency.

    Confirmed POs are left untouched on purpose.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    orders = env["purchase.order"].search(
        [("state", "in", ("draft", "sent")), ("fiscal_operation_id", "!=", False)]
    )
    orders = orders.filtered(lambda o: o.currency_id != o.company_id.currency_id)
    if not orders:
        return
    orders.order_line._compute_amount()
    orders._amount_all()
