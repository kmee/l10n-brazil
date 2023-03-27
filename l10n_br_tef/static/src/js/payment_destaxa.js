/*
    L10n_br_tef
    Copyright (C) 2018 KMEE INFORMATICA LTDA (http://www.kmee.com.br)
    @author Luis Felipe Mileo  <mileo@kmee.com.br>
    License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
*/

odoo.define("l10n_br_tef.PaymentVspague", function (require) {
    "use strict";

    var PaymentInterface = require("point_of_sale.PaymentInterface");

    var VspaguePaymentTerminal = PaymentInterface.extend({
        init: function () {
            this._super.apply(this, arguments);
            this.enable_reversals();
        },
        send_payment_request: function (cid) {
            this._super.apply(this, arguments);
            return this._vspague_payment_terminal_pay(cid);
        },
        send_payment_cancel: function (order, cid) {
            this._super.apply(this, arguments);
            return this._vspague_payment_terminal_cancel(order, cid);
        },
        send_payment_reversal: function (cid) {
            this._super.apply(this, arguments);
            return this._vspague_payment_terminal_reversal(cid);
        },
        close: function () {
            this._super.apply(this, arguments);
            return this._vspague_payment_terminal_close();
        },
        _vspague_payment_terminal_pay: async function (cid) {
            console.log("Vspague Pay");
            const selected_paymentline = this.pos.get_order().selected_paymentline;
            selected_paymentline.set_payment_status("waitingCard");

            const payment_mode = selected_paymentline.payment_method.vspague_payment_terminal_mode

            let operation = null;
            if (payment_mode in ['Credito', 'Debito']){
                operation = "Cartao Vender";
            } else if (payment_mode === 'Pix'){
                operation = "Digital Pagar";
            }

            if (!operation){
                // TODO: Show error popup
                console.error('Unable to determine payment operation.');
                return;
            }

            await this.pos.tef_client.start_operation(operation);
            const promise = new Promise((resolve, reject) => {
                selected_paymentline.resolve_pay_promise = resolve;
            });
            return promise;
        },
        _vspague_payment_terminal_cancel: function (order, cid) {
            this.pos.tef_client.abort();
            console.log("Vspague Cancel");
        },
        _vspague_payment_terminal_reversal: function (cid) {
            console.log("Vspague Reversal");
        },
        _vspague_payment_terminal_close: function () {
            console.log("Vspague Close");
        },
    });
    return VspaguePaymentTerminal;
});
