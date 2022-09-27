odoo.define("l10n_br_pos_cfe.OrderTotalsReceipt", function (require) {
    "use strict";

    const PosComponent = require("point_of_sale.PosComponent");
    const Registries = require("point_of_sale.Registries");
    const utils = require("web.utils");

    const round_pr = utils.round_precision;

    class OrderTotalsReceipt extends PosComponent {
        get order() {
            return this.props.order;
        }

        // Getters //

        get total_with_tax() {
            return this.order.total_with_tax;
        }

        get total_discount() {
            return this.order.total_discount;
        }

        get subtotal() {
            return this.subtotal_without_discount(this.order.orderlines);
        }

        subtotal_without_discount(orderlines) {
            return round_pr(
                orderlines.reduce((sum, line) => {
                    return sum + line.price * line.quantity;
                }, 0)
            );
        }
    }
    OrderTotalsReceipt.template = "OrderTotalsReceipt";

    Registries.Component.add(OrderTotalsReceipt);

    return OrderTotalsReceipt;
});
