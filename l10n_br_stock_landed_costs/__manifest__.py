# Copyright 2026 KMEE INFORMATICA LTDA - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Brazilian Localization Stock Landed Costs",
    "summary": "Landed costs from freight (CT-e) and expense fiscal documents,"
    " at the net acquisition cost",
    "category": "Localisation",
    "license": "AGPL-3",
    "author": "KMEE, Odoo Community Association (OCA)",
    "maintainers": ["mileo"],
    "website": "https://github.com/OCA/l10n-brazil",
    "development_status": "Beta",
    "version": "16.0.1.0.0",
    "depends": [
        "stock_landed_costs",
        "l10n_br_stock_account",
    ],
    "data": [
        "views/fiscal_document_view.xml",
        "views/stock_landed_cost_view.xml",
    ],
    "installable": True,
}
