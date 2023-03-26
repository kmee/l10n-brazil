# Copyright 2018 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "L10n Br Pos Cfe",
    "summary": """CF-e""",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "KMEE,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "category": "Point Of Sale",
    "development_status": "Alpha",
    "maintainers": ["mileo", "lfdivino", "luismalta", "ygcarvalh"],
    "depends": [
        "l10n_br_pos",
    ],
    "external_dependencies": {
        "python": ["satcomum"],
    },
    "data": [
        "views/pos_payment_method_view.xml",
    ],
    "demo": [
        "demo/pos_config_demo.xml",
        "demo/pos_payment_method_demo.xml",
    ],
    "installable": True,
    "assets": {
        "point_of_sale.assets": [
            "l10n_br_pos_cfe/static/src/js/**/*.js",
            "l10n_br_pos_cfe/static/src/xml/**/*.xml",
            "l10n_br_pos_cfe/static/src/css/pos.css",
        ],
    },
}
