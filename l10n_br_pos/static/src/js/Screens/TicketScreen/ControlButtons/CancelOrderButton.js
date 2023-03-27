odoo.define("l10n_br_pos.CancelOrderButton", function (require) {
    "use strict";

    const {useListener} = require("@web/core/utils/hooks");
    const PosComponent = require("point_of_sale.PosComponent");
    const Registries = require("point_of_sale.Registries");

    class CancelOrderButton extends PosComponent {
        setup() {
            super.setup();
            useListener("click", this._onClick);
        }
        async _show_edit_reason_popup() {
            const {confirmed, payload} = await this.showPopup("TextInputPopup", {
                title: this.env._t("Enter reason for cancellation!"),
            });
            if (confirmed) {
                return {
                    id: 999999,
                    cancel_reason: payload,
                };
            }
            return false;
        }
        async _show_selection_popup() {
            // TODO: Buscar motivos padrão da retaguarda;
            var cancel_reason = null;

            var selectionList = [
                {
                    id: 1,
                    item: {
                        // Any object!
                        id: 1,
                        cancel_reason: "Reason 1",
                    },
                    label: "Reason 1",
                    isSelected: false,
                },
                {
                    id: 999999,
                    item: {
                        // Any object!
                        id: 999999,
                    },
                    label: "Enter the reason",
                    isSelected: false,
                },
            ];

            const {confirmed, payload} = await this.showPopup("SelectionPopup", {
                title: this.env._t("Reason for Cancellation?"),
                list: selectionList,
            });
            if (confirmed) {
                if (payload.id === 999999) {
                    cancel_reason = await this._show_edit_reason_popup();
                    if (!cancel_reason) {
                        cancel_reason = await this._show_selection_popup();
                    }
                } else {
                    cancel_reason = payload;
                }
            }
            return cancel_reason;
        }
        async _onClick() {
            const order = this.props.order;
            if (!order) return;
            const cancel_reason = await this._show_selection_popup();
            if (cancel_reason) {
                const result = await order.document_cancel(cancel_reason, this);
                if (result) {
                    order.cancel_order(result);
                    this.showScreen("ReprintReceiptScreen", {order: order});
                } else {
                    this.document_event_messages.push({
                        id: 5001,
                        label: "Cancellation failed.",
                    });
                }
            }
        }
    }
    CancelOrderButton.template = "CancelOrderButton";
    Registries.Component.add(CancelOrderButton);

    return CancelOrderButton;
});
