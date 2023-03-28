odoo.define("l10n_br_pos_nfce.NfceOrderReceipt", function (require) {
    "use strict";

    const OrderReceipt = require("point_of_sale.OrderReceipt");
    const Registries = require("point_of_sale.Registries");

    const NfceOrderReceipt = (OrderReceipt) =>
        class extends OrderReceipt {
            get isHomologationEnvironment() {
                return this.receipt.nfce_environment === "2";
            }

            get hasChange() {
                return this.receipt.change;
            }

            get orderChange() {
                return this.receipt.change.toLocaleString("pt-br", {
                    minimumFractionDigits: 2,
                });
            }
        };

    Registries.Component.extend(OrderReceipt, NfceOrderReceipt);
    OrderReceipt.template = "NfceOrderReceipt";

    return OrderReceipt;
});
