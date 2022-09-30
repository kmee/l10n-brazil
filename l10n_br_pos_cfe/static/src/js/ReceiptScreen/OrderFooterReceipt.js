odoo.define("l10n_br_pos_cfe.OrderFooterReceipt", function (require) {
    "use strict";

    const PosComponent = require("point_of_sale.PosComponent");
    const Registries = require("point_of_sale.Registries");

    class OrderFooterReceipt extends PosComponent {
        get order() {
            return this.props.order;
        }

        // Getters //

        get document_key() {
            this.order.document_key_formatted = this.order.document_key.substring(3);
            return this.order.document_key_formatted;
        }

        get document_date() {
            return moment(this.order.authorization_date).format("YYYY/MM/DD hh:mm:ss");
        }
    }
    OrderFooterReceipt.template = "OrderFooterReceipt";

    Registries.Component.add(OrderFooterReceipt);

    return OrderFooterReceipt;
});
