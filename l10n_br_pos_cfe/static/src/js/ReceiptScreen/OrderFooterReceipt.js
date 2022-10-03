odoo.define("l10n_br_pos_cfe.OrderFooterReceipt", function (require) {
    "use strict";

    const PosComponent = require("point_of_sale.PosComponent");
    const Registries = require("point_of_sale.Registries");

    class OrderFooterReceipt extends PosComponent {
        mounted() {
            setTimeout(() => this._generateBarcode(this.getFormattedDocumentKey()), 0);
        }

        get order() {
            return this.props.order;
        }

        _generateBarcode(documentKey) {
            let s = 1;
            const barcode = document.getElementsByClassName("satBarcode");
            // eslint-disable-next-line
            const dm = datamatrix(documentKey, true);
            if (dm.length === 0) {
                s = 2;
                console.error("Message too long for Data Matrix.");
            } else {
                s = Math.floor((400 + dm[1].length) / dm[1].length);
                // eslint-disable-next-line
                barcode[0].innerHTML = toHtml(
                    // eslint-disable-next-line
                    [code128(documentKey)],
                    [(s / 4) | 0, 50]
                );
            }
        }

        getFormattedDocumentKey() {
            return this.order.document_key.replace("CFe", "");
        }

        // Getters //

        get satNumber() {
            return this.order.document_serie;
        }

        get document_key() {
            return this.getFormattedDocumentKey();
        }

        get document_date() {
            return moment(this.order.authorization_date).format("DD/MM/YYYY HH:mm:ss");
        }
    }
    OrderFooterReceipt.template = "OrderFooterReceipt";

    Registries.Component.add(OrderFooterReceipt);

    return OrderFooterReceipt;
});
