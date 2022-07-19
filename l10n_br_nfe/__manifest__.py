# Copyright (C) 2019  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html


{
    "name": "NF-e",
    "summary": "Brazilian Eletronic Invoice NF-e",
    "category": "Localisation",
    "license": "AGPL-3",
    "author": "Akretion," "KMEE," "Odoo Community Association (OCA)",
    "maintainers": ["rvalyi", "renatonlima"],
    "website": "https://github.com/OCA/l10n-brazil",
    "development_status": "Beta",
    "version": "14.0.8.0.1",
    "depends": [
        "l10n_br_fiscal",
        "l10n_br_nfe_spec",
        "spec_driven_model",
    ],
    "data": [
        # Data
        "data/ir_config_parameter.xml",
        # Security
        "security/nfe_security.xml",
        "security/ir.model.access.csv",
        # Views
        "views/res_company_view.xml",
        "views/nfe_document_view.xml",
        "views/res_config_settings_view.xml",
        # Wizards
        "wizards/import_document.xml",
        # Actions,
        "views/nfe_action.xml",
        # Menus
        "views/nfe_menu.xml",
    ],
    "demo": [
        "demo/res_users_demo.xml",
        "demo/fiscal_document_demo.xml",
        "demo/company_demo.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
    "external_dependencies": {
        "python": [
            "nfelib",
            "erpbrasil.base",
            "erpbrasil.assinatura",
            "erpbrasil.transmissao",
            "erpbrasil.edoc",
            "erpbrasil.edoc.pdf",
            "xmldiff",
        ],
    },
}
