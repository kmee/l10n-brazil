/*
Copyright (C) 2022-Today KMEE (https://kmee.com.br)
@author: Luis Felipe Mileo <mileo@kmee.com.br>
 License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
*/

odoo.define("l10n_br_pos.TicketScreen", function (require) {
    "use strict";

    const TicketScreen = require("point_of_sale.TicketScreen");
    const Registries = require("point_of_sale.Registries");

    const L10nBrPosTicketScreen = (TicketScreen) =>
        class extends TicketScreen {
            getDocumentSerieNumber(order) {
                if (order.document_serie && order.document_number) {
                    return (
                        order.document_type +
                        "/" +
                        order.document_serie +
                        "/" +
                        order.document_number
                    );
                }
                return null;
            }
            getPartner(order) {
                const cnpj_cpf = order.get_cnpj_cpf();
                if (cnpj_cpf) {
                    return cnpj_cpf;
                }
                return super.getPartner(...arguments);
            }
            getEdocState(order) {
                return order.get_situacao_edoc();
            }
        };

    Registries.Component.extend(TicketScreen, L10nBrPosTicketScreen);

    return L10nBrPosTicketScreen;
});
