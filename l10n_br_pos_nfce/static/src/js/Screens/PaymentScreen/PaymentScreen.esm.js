import {PaymentScreen} from "@point_of_sale/app/screens/payment_screen/payment_screen";
import {patch} from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    check_valid_cpf_cnpj(order) {
        const partner = order.get_partner();
        if (partner && partner.is_anonymous_consumer) {
            return true;
        }

        return super.check_valid_cpf_cnpj(...arguments);
    },

    shouldDownloadInvoice() {
        if (this.currentOrder.document_type_id?.code === "65") {
            return false;
        }

        return super.shouldDownloadInvoice(...arguments);
    },

    get nextScreen() {
        if (this.currentOrder.document_type_id?.code === "65") {
            return "ReceiptScreen";
        }
        return super.nextScreen;
    },
});
