odoo.define("l10n_br_pos_cfe.Printer", function (require) {
    "use strict";

    const { PrinterMixin, Printer } = require('point_of_sale.Printer');

    const L10nBrPosCfePrinterMixin = PrinterMixin.include({
        print_receipt: async function(receipt) {
            console.log("🚀 ~ file: printers.js:13 ~ print_receipt:function ~ receipt:", receipt)
            return this._super(receipt);
        }
    });

    const L10nBrPosCfePrinter = Printer.include({
        send_printing_job: function (img) {
            console.log("🚀 ~ file: printers.js:18 ~ img:", img)
            return this._super(img);
        },
    });

    return {
        PrinterMixin: L10nBrPosCfePrinterMixin,
        Printer: L10nBrPosCfePrinter
    };
});
