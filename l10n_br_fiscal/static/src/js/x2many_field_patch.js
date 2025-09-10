/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";

// This patch adds the complete 'views' object to the props passed to the ListRenderer.
patch(X2ManyField.prototype, {
    get rendererProps() {
        // This is the original method, we just add one more prop.
        const props = super.rendererProps;
        // Pass the sub-views (list, form, etc.) to the renderer
        props.views = this.props.views;
        return props;
    },
});
