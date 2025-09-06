/** @odoo-module **/
// Copyright 2025-TODAY Akretion - Raphael Valyi <raphael.valyi@akretion.com>
// License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).

/* eslint-disable sort-imports */

import { useBus } from "@web/core/utils/hooks"; // Import the useBus hook
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";
import { ViewButton } from "@web/views/view_button/view_button";

patch(ViewButton.prototype, {
    onClick() {
        if (this.props.className?.includes("edit-line-popup")) {
            if (this.props.record) {
                // Trigger the event on the record's model bus
                this.props.record.model.bus.trigger("OPEN_LINE_IN_POPUP", {
                    record: this.props.record,
                });
            }
            return;
        }
        return super.onClick(...arguments);
    },
});

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);

        // Use the 'useBus' hook to listen for the event on the list's model bus.
        // The hook automatically handles cleaning up the listener when the component is destroyed.
        useBus(this.props.list.model.bus, "OPEN_LINE_IN_POPUP", (ev) => {
            const { record } = ev.detail; // The payload is in the 'detail' property of the event
            if (this.props.list.records.includes(record)) {
                this.props.openRecord(record);
            }
        });
    },
});
