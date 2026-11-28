# Copyright 2026 KMEE (https://www.kmee.com.br)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Brazilian Localization NF-e Origin Notes",
    "summary": "Number of the origin notes in the NF-e additional information",
    "category": "Localisation",
    "license": "AGPL-3",
    "author": "KMEE, Odoo Community Association (OCA)",
    "maintainers": ["mileo"],
    "website": "https://github.com/OCA/l10n-brazil",
    "version": "18.0.1.0.0",
    "development_status": "Beta",
    "depends": [
        "l10n_br_nfe",
    ],
    "data": [
        "views/fiscal_operation_view.xml",
        "views/document_view.xml",
    ],
    "demo": [
        "demo/fiscal_operation_demo.xml",
        "demo/document_demo.xml",
    ],
    "installable": True,
}
