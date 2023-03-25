/*
Copyright (C) 2016-Today KMEE (https://kmee.com.br)
@author: Luis Felipe Mileo <mileo@kmee.com.br>
 License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
*/

odoo.define("l10n_br_pos.models", function (require) {
    "use strict";

    const {PosGlobalState, Order, Orderline, Payment} = require("point_of_sale.models");
    const Registries = require("point_of_sale.Registries");

    const utils = require("web.utils");
    const util = require("l10n_br_pos.util");
    const {Gui} = require("point_of_sale.Gui");
    const {_t} = require("web.core");

    const round_pr = utils.round_precision;

    const SITUACAO_EDOC_EM_DIGITACAO = "em_digitacao";
    const SITUACAO_EDOC_A_ENVIAR = "a_enviar";
    const SITUACAO_EDOC_ENVIADA = "enviada";
    const SITUACAO_EDOC_REJEITADA = "rejeitada";
    const SITUACAO_EDOC_AUTORIZADA = "autorizada";
    const SITUACAO_EDOC_CANCELADA = "cancelada";
    const SITUACAO_EDOC_DENEGADA = "denegada";
    const SITUACAO_EDOC_INUTILIZADA = "inutilizada";

    const SITUACAO_EDOC = {
        [SITUACAO_EDOC_EM_DIGITACAO]: "Em digitação",
        [SITUACAO_EDOC_A_ENVIAR]: "Aguardando envio",
        [SITUACAO_EDOC_ENVIADA]: "Aguardando processamento",
        [SITUACAO_EDOC_REJEITADA]: "Rejeitada",
        [SITUACAO_EDOC_AUTORIZADA]: "Autorizada",
        [SITUACAO_EDOC_CANCELADA]: "Cancelada",
        [SITUACAO_EDOC_DENEGADA]: "Denegada",
        [SITUACAO_EDOC_INUTILIZADA]: "Inutilizada",
    };

    const L10nBrPosGlobalState = (PosGlobalState) =>
        class L10nBrPosGlobalState extends PosGlobalState {
            constructor(obj) {
                super(obj);
                this.cnpj_cpf = false;
                this.last_document_session_number = false;
            }

            async _processData(loadedData) {
                await super._processData(...arguments);
                this.fiscal_map = loadedData["l10n_br_pos.product_fiscal_map"];
            }

            get_cnpj_cpf() {
                var order = this.get_order();
                if (order) {
                    return order.get_cnpj_cpf();
                }
                return null;
            }
        };

    Registries.Model.extend(PosGlobalState, L10nBrPosGlobalState);

    const L10nBrPosOrder = (Order) =>
        class L10nBrPosOrder extends Order {
            constructor(obj, options) {
                super(...arguments);
                this.init_locked = true;

                var company = this.pos.company;
                this.document_company = {};
                this.document_company.cnpj = company.cnpj || null;
                this.document_company.ie = company.ie || null;
                this.document_company.tax_framework = company.tax_framework || null;

                if (!options.json) {
                    this.status_code = this.status_code || null;
                    this.status_name = this.status_name || null;
                    this.status_description = this.status_description || null;
                    this.authorization_date = this.authorization_date || null;
                    this.authorization_protocol = this.authorization_protocol || null;
                    this.authorization_file = this.authorization_file || null;
                    this.cancel_date = this.cancel_date || null;
                    this.cancel_protocol_number = this.cancel_protocol_number || null;
                    this.cancel_file = this.cancel_file || null;
                    this.is_edoc_printed = this.is_edoc_printed || null;
                    this.state_edoc = this.state_edoc || SITUACAO_EDOC_EM_DIGITACAO;
                    this.document_number = this.document_number || null;
                    this.document_serie = this.document_serie || null;
                    this.document_session_number = this.document_session_number || null;
                    this.document_rps_number = this.document_rps_number || null;
                    this.document_key = this.document_key || null;
                    this.document_date = this.document_date || null;
                    this.document_electronic = this.document_electronic || null;
                    this.document_qrcode_signature =
                        this.document_qrcode_signature || null;
                    this.document_qrcode_url = this.document_qrcode_url || null;
                    this.cnpj_cpf = this.cnpj_cpf || null;
                    this.fiscal_operation_id =
                        this.pos.config.out_pos_fiscal_operation_id[0] || null;
                    this.document_type_id =
                        this.pos.config.simplified_document_type_id[0] || null;
                    this.document_type =
                        this.pos.config.simplified_document_type || null;
                }
                this.document_event_messages = this.document_event_messages || [];
                this.init_locked = false;
            }

            init_from_JSON(json) {
                super.init_from_JSON(...arguments);
                this.status_code = json.status_code;
                this.status_name = json.status_name;
                this.status_description = json.status_description;
                this.authorization_date = json.authorization_date;
                this.authorization_protocol = json.authorization_protocol;
                this.authorization_file = json.authorization_file;
                this.cancel_date = json.cancel_date;
                this.cancel_protocol_number = json.cancel_protocol_number;
                this.cancel_file = json.cancel_file;
                this.is_edoc_printed = json.is_edoc_printed;
                this.state_edoc = json.state_edoc;
                this.document_number = json.document_number;
                this.document_serie = json.document_serie;
                this.document_session_number = json.document_session_number;
                this.document_rps_number = json.document_rps_number;
                this.document_key = json.document_key;
                this.document_date = json.document_date;
                this.document_electronic = json.document_electronic;
                this.document_qrcode_signature = json.document_qrcode_signature;
                this.document_qrcode_url = json.document_qrcode_url;
                this.cnpj_cpf = json.cnpj_cpf;
                this.fiscal_operation_id = json.fiscal_operation_id;
                this.document_type_id = json.document_type_id;
                this.document_type = json.document_type;
            }

            _prepare_fiscal_json(json) {
                // Company details
                json.company = this.document_company || {};

                // Document data
                json.status_code = this.status_code;
                json.status_name = this.status_name;
                json.status_description = this.status_description;

                json.authorization_date = this.authorization_date;
                json.authorization_protocol = this.authorization_protocol;
                json.authorization_file = this.authorization_file;

                json.cancel_document_key = this.cancel_document_key;
                json.cancel_date = this.cancel_date;
                json.cancel_protocol_number = this.cancel_protocol_number;
                json.cancel_file = this.cancel_file;
                json.cancel_qrcode_signature = this.cancel_qrcode_signature;

                json.is_edoc_printed = this.is_edoc_printed;

                // L10n_br_fiscal.document fields

                json.state_edoc = this.state_edoc;
                json.document_number = this.document_number;
                json.document_serie = this.document_serie;
                json.document_session_number = this.document_session_number;
                json.document_rps_number = this.document_rps_number;

                json.document_key = this.document_key;
                json.document_date = this.document_date;
                json.document_electronic = this.document_electronic;

                // NFC-e & CF-e fields

                json.document_qrcode_signature = this.document_qrcode_signature;
                json.document_qrcode_url = this.document_qrcode_url;

                // Field where messages from the communication process are stored.
                json.document_event_messages = this.document_event_messages || [];

                json.fiscal_operation_id =
                    this.pos.config.out_pos_fiscal_operation_id[0];
                json.document_type_id = this.pos.config.simplified_document_type_id[0];
                json.document_type = this.pos.config.simplified_document_type;

                // Customer data
                // json.client = this.cnpj_cpf;
                json.cnpj_cpf = this.get_cnpj_cpf();

                // Additional document data
                if (this.pos.config.additional_data) {
                    var taxes = this.get_taxes_and_percentages(json);
                    json.additional_data = this.compute_message(
                        this.pos.config.additional_data,
                        taxes
                    );
                } else {
                    json.additional_data = null;
                }
            }

            export_as_JSON() {
                // Export_as_JSON method must have only necessary data to issue the tax coupon
                const json = super.export_as_JSON(...arguments);
                // Remove lines without price
                json.lines = _.filter(json.lines, function (line) {
                    return line[2].price_subtotal !== 0 || line[2].qty !== 0;
                });
                this._prepare_fiscal_json(json);
                return json;
            }

            export_for_printing() {
                const json = super.export_for_printing(...arguments);
                // Remove lines without price
                json.orderlines = _.filter(json.orderlines, function (line) {
                    return line.price !== 0 || line.quantity !== 0;
                });
                // Remove reversed paymentlines
                json.paymentlines = _.filter(json.paymentlines, function (line) {
                    return line.payment_status !== "reversed";
                });
                this._prepare_fiscal_json(json);
                return json;
            }

            clone() {
                const order = super.clone(...arguments);
                order.cnpj_cpf = null;
                return order;
            }

            set_cnpj_cpf(cnpj_cpf) {
                if (util.validate_cnpj_cpf(cnpj_cpf)) {
                    this.assert_editable();
                    this.cnpj_cpf = cnpj_cpf;
                    this.trigger("change", this);
                    return true;
                }
                this.pos.gui.show_popup("alert", {
                    title: _t("Invalid CNPJ / CPF !"),
                    body: _t("Enter a valid CNPJ / CPF number"),
                });
                return false;
            }

            get_client() {
                return this.partner;
            }

            get_cnpj_cpf() {
                var partner_vat = null;
                if (this.get_client() && this.get_client().vat) {
                    partner_vat = this.get_client().vat;
                }
                return this.cnpj_cpf || partner_vat;
            }

            get_taxes_and_percentages() {
                var taxes = {
                    federal: {
                        percent: 0,
                        total: 0,
                    },
                    estadual: {
                        percent: 0,
                        total: 0,
                    },
                };
                const rounding = this.pos.currency.rounding;
                var line = order.orderlines[0];
                taxes.federal.percent = line.cofins_percent + line.pis_percent;
                taxes.federal.total = round_pr(
                    order.total_paid * (taxes.federal.percent / 100),
                    rounding
                );
                taxes.estadual.percent = line.icms_percent;
                taxes.estadual.total = round_pr(
                    order.total_paid * (taxes.estadual.percent / 100),
                    rounding
                );

                return taxes;
            }

            compute_message(templateString, taxes) {
                /* Compute fiscal message */
                return new Function(`return \`${templateString}\`;`).call(this, taxes);
            }

            _document_status_popup() {
                var msgs = [];
                this.document_event_messages.forEach((element) => {
                    msgs.push({
                        id: element.id,
                        label: element.label,
                        item: element.id,
                    });
                });
            }

            async document_send(component) {
                this.state_edoc = SITUACAO_EDOC_A_ENVIAR;
                component.showNotification(
                    _.str.sprintf(
                        this.pos.env._t("Iniciando o processo de transmissão")
                    ),
                    1000
                );
                this._document_status_popup();
                var result = false;
                var processor_result = null;
                // Check if fields of fiscal document are valid.
                result = await this._document_validate(component);
                if (result) {
                    // Get the person responsible for sending the fiscal document;
                    var processor = await this._document_get_processor(component);
                    if (processor) {
                        // Send fiscal document
                        processor_result = await processor.send_order(this);
                        // Validate if it was issued correctly and saves the result data
                        result = await this._document_check_result(
                            processor_result,
                            component
                        );
                    } else {
                        Gui.showPopup("ErrorPopup", {
                            title: this.pos.env._t("Error"),
                            body: this.pos.env._t("Sem processador localizado"),
                        });
                        result = false;
                    }
                } else {
                    Gui.showPopup("ErrorPopup", {
                        title: this.pos.env._t("Error"),
                        body: this.pos.env._t(
                            "Erro na validação do documento de emissão"
                        ),
                    });
                }
                return result;
            }

            async _document_validate(component) {
                return true;
            }

            async _document_get_processor(component) {
                return null;
            }

            async _document_check_result(processor_result, component) {
                this.state_edoc = SITUACAO_EDOC_AUTORIZADA;
                return true;
            }

            async _document_cancel_validate(component) {
                return true;
            }

            async _document_cancel_check_result(processor_result, component) {
                this.state_edoc = SITUACAO_EDOC_CANCELADA;
                return true;
            }

            async document_cancel(cancel_reason, component) {
                this.cancel_reason = cancel_reason;
                component.showNotification(
                    _.str.sprintf(this.pos.env._t("Cancelando o documento fiscal")),
                    1000
                );
                var result = false;
                var processor_result = null;
                result = await this._document_cancel_validate(component);
                if (result) {
                    // Get the person responsible for sending the fiscal document;
                    var processor = await this._document_get_processor(component);
                    if (processor) {
                        // Calcel the fiscal document
                        processor_result = await processor.cancel_order(this);
                        // Validate if it was issued correctly and saves the result data
                        result = await this._document_cancel_check_result(
                            processor_result,
                            component
                        );
                    } else {
                        Gui.showPopup("ErrorPopup", {
                            title: this.pos.env._t("Error"),
                            body: this.pos.env._t("Sem processador localizado"),
                        });
                        return false;
                    }
                } else {
                    Gui.showPopup("ErrorPopup", {
                        title: this.pos.env._t("Error"),
                        body: this.pos.env._t(
                            "Erro na validação do cancelamento do cupom"
                        ),
                    });
                }
                return result;
            }

            get_situacao_edoc() {
                if (this.state_edoc) {
                    return SITUACAO_EDOC[this.state_edoc];
                }
                return "";
            }

            cancel_order(result) {
                try {
                    this.pos.env.services.rpc({
                        model: "pos.order",
                        method: "cancel_order",
                        args: [result.response],
                    });
                } catch (error) {
                    if (
                        error.message &&
                        [100, 200, 404, -32098].includes(error.message.code)
                    ) {
                        Gui.showPopup("ErrorPopup", {
                            title: this.pos.comp.env._t("Network Error"),
                            body: this.pos.comp.env._t(
                                "Unable to update values in backend if offline."
                            ),
                        });
                        Gui.setSyncStatus("error");
                    } else {
                        throw error;
                    }
                }
            }

            decode_cancel_xml(XmlEncoded) {
                return decodeURIComponent(atob(XmlEncoded));
            }
        };

    Registries.Model.extend(Order, L10nBrPosOrder);

    const L10nBrPosOrderLine = (Orderline) =>
        class L10nBrPosOrderLine extends Orderline {
            _prepare_fiscal_json(json) {
                var self = this;
                var product = this.get_product();
                var product_fiscal_map = this._findFiscalMap(product.product_tmpl_id);

                json.cest_id = product.cest_id;
                json.city_taxation_code_id = product.city_taxation_code_id;
                json.fiscal_genre_code = product.fiscal_genre_code;
                json.fiscal_genre_id = product.fiscal_genre_id;
                json.fiscal_type = product.fiscal_type;
                json.icms_origin = product.icms_origin;
                json.ipi_control_seal_id = product.ipi_control_seal_id;
                json.ipi_guideline_class_id = product.ipi_guideline_class_id;
                json.nbs_id = product.nbs_id;
                json.product_default_code = product.default_code;
                json.product_ean = product.barcode;
                json.service_type_id = product.service_type_id;
                json.tax_icms_or_issqn = product.tax_icms_or_issqn;
                json.unit_code = this.get_unit().code;

                if (product_fiscal_map) {
                    json.additional_data = product_fiscal_map.additional_data || "";
                    json.amount_estimate_tax =
                        product_fiscal_map.amount_estimate_tax || 0;
                    json.cfop = product_fiscal_map.cfop_code;
                    json.cofins_base = product_fiscal_map.cofins_base;
                    json.cofins_cst_code = product_fiscal_map.cofins_cst_code;
                    json.cofins_percent = product_fiscal_map.cofins_percent;
                    json.company_tax_framework =
                        product_fiscal_map.company_tax_framework;
                    json.icms_cst_code = product_fiscal_map.icms_cst_code;
                    json.icms_effective_percent =
                        product_fiscal_map.icms_effective_percent;
                    json.icms_percent = product_fiscal_map.icms_percent;
                    json.icmssn_percent = product_fiscal_map.icmssn_percent;
                    json.ncm =
                        product_fiscal_map.ncm_code === "00000000"
                            ? "99999999"
                            : product_fiscal_map.ncm_code;
                    json.ncm_code_exception = product_fiscal_map.ncm_code_exception;
                    json.pis_base = product_fiscal_map.pis_base;
                    json.pis_cst_code = product_fiscal_map.pis_cst_code;
                    json.pis_percent = product_fiscal_map.pis_percent;
                }
            }

            export_for_printing() {
                const json = super.export_for_printing(...arguments);
                this._prepare_fiscal_json(json);
                return json;
            }

            _findFiscalMap(productTemplateID) {
                return Object.values(this.pos.fiscal_map).filter(
                    (item) => item.product_tmpl_id[0] === productTemplateID
                )[0];
            }
        };

    Registries.Model.extend(Orderline, L10nBrPosOrderLine);

    const L10nBrPosPayment = (Payment) =>
        class L10nBrPosPayment extends Payment {
            _prepare_fiscal_json(json) {
                json.payment_status = this.payment_status;
            }

            export_for_printing() {
                const json = super.export_for_printing(...arguments);
                this._prepare_fiscal_json(json);
                return json;
            }
        };

    Registries.Model.extend(Payment, L10nBrPosPayment);
});
