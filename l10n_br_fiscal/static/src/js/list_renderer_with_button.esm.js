/** @odoo-module **/
// Copyright 2025-TODAY Akretion - Raphael Valyi <raphael.valyi@akretion.com>
// License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).

/* eslint-disable sort-imports */

import {patch} from "@web/core/utils/patch";
import {useBus} from "@web/core/utils/hooks";
import {X2ManyField} from "@web/views/fields/x2many/x2many_field";
import {ViewButton} from "@web/views/view_button/view_button";

patch(ViewButton.prototype, {
    onClick() {
        if (this.props.className && this.props.className.includes("edit-line-popup")) {
            if (this.props.record) {
                this.env.bus.trigger("OPEN_LINE_IN_POPUP", {
                    record: this.props.record,
                });
            }
            return;
        }
        super.onClick(...arguments);
    },
});

patch(X2ManyField.prototype, {
    setup() {
        super.setup(...arguments);
        useBus(this.env.bus, "OPEN_LINE_IN_POPUP", (ev) => {
            const record = ev.detail.record;
            if (this.list.records.includes(record)) {
                this._openRecord({
                    record,
                    context: this.props.context,
                    mode: this.props.readonly ? "readonly" : "edit",
                });
            }
        });
    },
});
