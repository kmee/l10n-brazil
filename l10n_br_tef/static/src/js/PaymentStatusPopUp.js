odoo.define('l10n_br_tef.PaymentStatusPopUp', function(require) {
    'use strict';

    const AbstractAwaitablePopup = require('point_of_sale.AbstractAwaitablePopup');
    const Registries = require('point_of_sale.Registries');
    const { _lt } = require('@web/core/l10n/translation');

    const { onMounted, useRef, useState } = owl;

    // formerly TextAreaPopupWidget
    // IMPROVEMENT: This code is very similar to TextInputPopup.
    //      Combining them would reduce the code.
    class PaymentStatusPopUp extends AbstractAwaitablePopup {
        /**
         * @param {Object} props
         * @param {string} props.startingValue
         */
        setup() {
            super.setup();
            // this.state = useState({ inputValue: this.props.startingValue });
            // this.inputRef = useRef('input');
            onMounted(this.onMounted);
        }
        // onMounted() {
        //     this.inputRef.el.focus();
        // }
        // getPayload() {
        //     return this.state.inputValue;
        // }
    }
    PaymentStatusPopUp.template = 'PaymentStatusPopUp';
    PaymentStatusPopUp.defaultProps = {
        message: '',
        comment: '',
    };

    Registries.Component.add(PaymentStatusPopUp);

    return PaymentStatusPopUp;
});
