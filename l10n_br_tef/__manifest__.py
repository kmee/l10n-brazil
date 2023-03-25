# Copyright (C) 2018 KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

{
    "name": "l10n_br_tef",
    "version": "16.0.1.0.0",
    "category": "Point Of Sale",
    "summary": "Manage Payment TEF device from POS",
    "author": "KMEE, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/l10n-brazil",
    "depends": [
        "point_of_sale",
    ],
    "data": [
        "views/res_config_settings_view.xml",
        "views/pos_payment_method_view.xml",
    ],
    "assets": {
        "point_of_sale.assets": [
            "l10n_br_tef/static/src/js/**/*.js",
            "l10n_br_tef/static/src/css/**/*.css",
            "l10n_br_tef/static/src/xml/**/*.xml",
        ],
    },
}
