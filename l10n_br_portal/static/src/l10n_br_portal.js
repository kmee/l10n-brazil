/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";

const portalDetails = publicWidget.registry.portalDetails;

portalDetails.include({
    selector: ".o_portal_details",
    events: {
        ...portalDetails.prototype.events,
        "change select[name='state_id']": "_onChangeState",
        "change input[name='zipcode']": "_onChangeZip",
    },

    init() {
        this._super(...arguments);
        this.rpc = this.bindService("rpc");
        this.notification = this.bindService("notification");
    },

    start() {
        this.$country = this.$("select[name='country_id']");
        this.$city = this.$("select[name='city_id']");
        this.$cityOptions = this.$("select[name='city_id']:enabled option:not(:first)");
        const def = this._super.apply(this, arguments);

        this.cleaveCNPJ = new Cleave(".input-cnpj-cpf", {
            blocks: [2, 3, 3, 4, 2],
            delimiters: [".", ".", "-"],
            numericOnly: true,
            onValueChanged: function (e) {
                if (e.target.rawValue.length > 11) {
                    this.properties.blocks = [2, 3, 3, 4, 2];
                    this.properties.delimiters = [".", ".", "/", "-"];
                } else {
                    this.properties.blocks = [3, 3, 3, 3];
                    this.properties.delimiters = [".", ".", "-"];
                }
            },
        });

        this.cleaveZipCode = new Cleave("input[name='zipcode']", {
            blocks: [5, 3],
            delimiter: "-",
            numericOnly: true,
        });
        return def.then(() => this._onChangeState());
    },

    _adaptAddressForm() {
        this._super.apply(this, arguments);
        this._onChangeState();
    },

    _onChangeState() {
        this.$cityOptions.detach();
        const displayedState = this.$cityOptions.filter(
            "[data-state_id=" + (this.$state.val() || 0) + "]"
        );
        const nb = displayedState.appendTo(this.$city).show().length;
        this.$city.parent().toggle(nb >= 1);
    },

    async _onChangeZip() {
        const data = await this.rpc(
            "/l10n_br/zip_search", 
            {zipcode: this.$('input[name="zipcode"]').val()}
        );
        if (data.error) {
            this.notification.add(_t("Zip is invalid or ."));
        } else {
            this.$('input[name="district"]').val(data.district);
            this.$('input[name="street_name"]').val(data.street_name);
            this.$country.val(data.country_id);
            this.$country.change();
            this.$state.val(data.state_id);
            this.$state.change();
            this.$city.val(data.city_id);
        }
    },

});