# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "NF-e Traceability (rastro)",
    "summary": "Fill the NF-e traceability group (rastro) from the stock lots",
    "version": "18.0.1.0.0",
    "category": "Localisation",
    "license": "AGPL-3",
    "author": "KMEE, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "development_status": "Beta",
    "depends": [
        "l10n_br_nfe",
        "l10n_br_stock_account",
        "product_expiry",
        "stock_lot_production_date",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/nfe_rastro_view.xml",
        "views/document_line_view.xml",
        "views/account_move_view.xml",
    ],
    "demo": [
        "demo/nfe_rastro_demo.xml",
    ],
    "installable": True,
}
