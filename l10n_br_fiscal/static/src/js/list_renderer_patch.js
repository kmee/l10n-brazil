/** @odoo-module **/

import { useBus, useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialogService = useService("dialog");

        useBus(this.env.bus, "OPEN_LINE_IN_POPUP", (ev) => {
            const { record: receivedRecord } = ev.detail;
            const recordInList = this.props.list.records.find(
                (r) => r.id === receivedRecord.id
            );

            if (recordInList) {
                this.openRecordInDialog(recordInList);
            }
        });
    },

    /**
     * Manually opens the correct inline FormViewDialog for a given record.
     */
    openRecordInDialog(record) {
        const list = this.props.list;
        
        // This now works because of the X2ManyField patch.
        const formView = this.props.views.form;
        if (!formView) {
            console.error("No inline form view defined for this list. Cannot open popup.");
            return;
        }

        this.dialogService.add(FormViewDialog, {
            resModel: list.resModel,
            resId: record.resId || false,
            context: record.context,
            title: record.resId ? "Edit Line" : "New Line",
            
            // THE KEY FIX: Use the fields and models from the FORM VIEW definition,
            // not from the list. This prevents the RPC error.
            fields: formView.fields,
            relatedModels: formView.relatedModels,
            arch: formView.arch,
            viewId: formView.view_id, // Pass the specific form view ID if available

            // Pass the record itself so the dialog edits our in-memory object
            record,

            onRecordSaved: () => {}, // Changes are applied to the in-memory record
            onRecordDiscarded: () => {
                if (record.isNew) {
                    list.delete(record);
                } else {
                    record.discard();
                }
            },
        });
    },
});
