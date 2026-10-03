# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "NF-e Medicines (med)",
    "summary": "ANVISA code and maximum consumer price of medicines in the NF-e",
    "version": "18.0.1.0.0",
    "category": "Localisation",
    "license": "AGPL-3",
    "author": "KMEE, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "development_status": "Beta",
    "depends": [
        "l10n_br_nfe_rastro",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/nfe_med_view.xml",
        "views/product_template_view.xml",
        "views/document_line_view.xml",
        "views/account_move_view.xml",
    ],
    "demo": [
        "demo/nfe_med_demo.xml",
    ],
    "installable": True,
}
