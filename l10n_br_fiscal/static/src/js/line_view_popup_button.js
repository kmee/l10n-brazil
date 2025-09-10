/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class LineViewPopupButton extends Component {
    static template = "l10n_br_account.LineViewPopupButton";
    static props = { ...standardFieldProps };

    setup() {
        // This log will confirm the widget is being created for each row.
        console.log("LineViewPopupButton setup for record:", this.props.record.resId);
    }

    onClick() {
        // This log will now appear thanks to ".stop" in the template.
        console.log("LineViewPopupButton onClick triggered for record:", this.props.record.resId);
        if (this.props.record) {
            this.env.bus.trigger("OPEN_LINE_IN_POPUP", {
                record: this.props.record,
            });
        }
    }
}

export const lineViewPopupButton = {
    component: LineViewPopupButton,
};

registry.category("view_widgets").add("line_view_popup_button", lineViewPopupButton);
