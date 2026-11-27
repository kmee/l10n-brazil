# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal.constants.fiscal import TAX_DOMAIN_ISSQN


class SaleOrder(models.Model):
    _inherit = "sale.order"

    installment_surcharge_total = fields.Monetary(
        copy=False,
        readonly=True,
        help="What the installment interest charged by the company adds to the "
        "total of the order: the interest and the taxes computed on it.",
    )

    def _has_fiscal_installment_surcharge(self):
        """Whether the interest goes into the fiscal fields of the order.

        The Brazilian fiscal documents have no line for the interest: on the
        NF-e and the NFC-e it is part of the other costs (vOutro) of the goods.
        """
        self.ensure_one()
        return bool(self.fiscal_operation_id)

    @api.depends("installment_surcharge_total")
    def _compute_installment_surcharge_amount(self):
        res = super()._compute_installment_surcharge_amount()
        for order in self:
            if order._has_fiscal_installment_surcharge():
                order.installment_surcharge_amount += order.installment_surcharge_total
        return res

    def _can_take_installment_surcharge(self, amount=None):
        """Services are left out: the NFS-e has no field for other costs and
        they are not part of the ISS base."""
        res = super()._can_take_installment_surcharge(amount=amount)
        if not res or not self._has_fiscal_installment_surcharge():
            return res
        lines = self.order_line.filtered(lambda line: not line.display_type)
        return bool(self._get_product_amount_lines()) and not any(
            line.tax_icms_or_issqn == TAX_DOMAIN_ISSQN for line in lines
        )

    def _set_installment_surcharge(self, plan_line, amount):
        """Spread the interest over the other costs of the goods.

        No line is added to the order: the fiscal engine adds the other costs to
        the total of each line and to the tax bases, and they follow the order
        to the invoice and to the fiscal document.

        :param float amount: What the interest adds to the total of the order.
        """
        self.ensure_one()
        if not self._has_fiscal_installment_surcharge():
            return super()._set_installment_surcharge(plan_line, amount)

        # A line left by a choice made before the order became a fiscal one.
        self._get_installment_surcharge_lines().unlink()
        self._write_installment_surcharge_values({})
        self.installment_surcharge_total = 0.0
        if self.currency_id.is_zero(amount or 0.0):
            return self.env["sale.order.line"]

        # Taxes that are not included in the price (IPI) are computed on the
        # other costs too. The payer was shown the amount plus the interest, so
        # the other costs are set to what makes the total grow by the interest,
        # taxes included.
        total_before = self.amount_total
        other_costs = amount
        for _attempt in range(3):
            self._write_installment_surcharge_values(
                self._distribute_installment_surcharge(other_costs)
            )
            added = self.currency_id.round(self.amount_total - total_before)
            if (
                self.currency_id.is_zero(added - amount)
                or self.currency_id.compare_amounts(added, 0.0) <= 0
            ):
                break
            other_costs = self.currency_id.round(other_costs * amount / added)
        self.installment_surcharge_total = self.currency_id.round(
            self.amount_total - total_before
        )
        return self.env["sale.order.line"]

    def _distribute_installment_surcharge(self, amount):
        """Share the interest between the goods, by gross amount.

        Same rule as the freight, insurance and other costs set on the total of
        a fiscal document: the last line takes the rounding difference.

        :return: The share of each line.
        :rtype: dict[sale.order.line, float]
        """
        self.ensure_one()
        lines = self._get_product_amount_lines().filtered(
            lambda line: not line.display_type
        )
        total_gross = sum(lines.mapped("price_gross"))
        if not lines or self.currency_id.compare_amounts(total_gross, 0.0) <= 0:
            raise UserError(
                _("The order has no goods to add the installment interest to.")
            )
        shares = {}
        distributed = 0.0
        for line in lines[:-1]:
            shares[line] = self.currency_id.round(
                amount * line.price_gross / total_gross
            )
            distributed += shares[line]
        shares[lines[-1]] = self.currency_id.round(amount - distributed)
        return shares

    def _write_installment_surcharge_values(self, shares):
        """Replace the share of interest held in the other costs of the lines.

        Other costs the lines already had are kept. When the company informs
        the costs by total, the total is what is stored and the fiscal engine
        spreads it over the lines.

        :param dict shares: The new share of each line; a missing line gets none.
        """
        self.ensure_one()
        by_total = (
            self.delivery_costs == "total"
            or self.force_compute_delivery_costs_by_total
        )
        difference = 0.0
        for line in self.order_line:
            new = shares.get(line, 0.0)
            old = line.installment_surcharge_value
            if self.currency_id.is_zero(new - old):
                continue
            values = {"installment_surcharge_value": new}
            if not by_total:
                values["other_value"] = line.other_value - old + new
            line.write(values)
            difference += new - old
        if by_total and not self.currency_id.is_zero(difference):
            self.amount_other_value = self.amount_other_value + difference
