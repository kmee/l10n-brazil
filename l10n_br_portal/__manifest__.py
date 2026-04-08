# Copyright 2019 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "L10n Br Portal",
    "summary": """
        Campos Brasileiros no Portal""",
    "version": "18.0.2.1.1",
    "license": "AGPL-3",
    "author": "KMEE,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "development_status": "Production/Stable",
    "depends": [
        "portal",
        "l10n_br_zip",
    ],
    "demo": [
        "demo/res_users_demo.xml",
    ],
    "data": [
        "views/portal_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "/l10n_br_portal/static/src/l10n_br_portal.esm.js",
            "/l10n_br_portal/static/lib/cleave/cleave.min.js",
        ],
        "web_tour.assets_tour": [
            "/l10n_br_portal/static/tests/tours/l10n_br_portal_tour.esm.js",
        ],
    },
    "auto_install": True,
}
