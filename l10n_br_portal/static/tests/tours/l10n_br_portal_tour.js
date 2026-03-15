/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("l10n_br_portal_tour", {
    url: "/my/account",
    test: true,
    steps: () => [
        {
            content: "Complete name",
            trigger: "input[name='name']",
            run: "text Mileo",
        },
        {
            content: "Complete Legal Name",
            trigger: "input[name='legal_name']",
            run: "text Luis Felipe Mileo",
        },
        {
            content: "Complete CPF",
            trigger: "input[name='cnpj_cpf']",
            run: "text 89604455095",
        },
        {
            content: "Complete IE",
            trigger: "input[name='inscr_est']",
            run: "text ISENTO",
        },
        {
            content: "Complete Phone",
            trigger: "input[name='phone']",
            run: "text 45985092231",
        },
        {
            content: "Complete ZIP",
            trigger: "input[name='zipcode']",
            run: "text 37500015",
        },
        {
            content: "Complete Street Number",
            trigger: "input[name='street_number']",
            run: "text 12",
        },
        {
            content: "check city is Itajubá",
            trigger: 'select[name=city_id]:contains("Itajubá")',
            run: function () {
                /* Keep empty ... */
            },
        },
        {
            trigger: "button[type='submit']",
        },
        {
            content: "Go /my url",
            trigger: 'a[href*="/my"]',
        },
    ],
});