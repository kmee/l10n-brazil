# Copyright 2019 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Integração com API dos Correios",
    "summary": """
        Integração com API dos Correios""",
    "version": "14.0.1.0.1",
    "license": "AGPL-3",
    "author": "KMEE, Odoo Community Association (OCA)",
    "maintainers": ["andremarcos"],
    "website": "https://github.com/OCA/l10n-brazil",
    "development_status": "Beta",
    "depends": ["delivery_package_number", "delivery_state"],
    "data": [
        # "security/ir.model.access.csv",
        "views/delivery_correios_view.xml",
        # "views/res_company_view.xml",
        # "views/res_config_settings_view.xml",
    ],
}
