# Copyright 2026 KMEE INFORMATICA LTDA - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "DUIMP Landed Costs",
    "summary": "Customs expenses of a DUIMP as landed costs on its receipts,"
    " split by customs value",
    "category": "Localisation",
    "license": "AGPL-3",
    "author": "KMEE, Odoo Community Association (OCA)",
    "maintainers": ["mileo"],
    "website": "https://github.com/OCA/l10n-brazil",
    "development_status": "Alpha",
    "version": "18.0.1.0.0",
    "depends": [
        "l10n_br_duimp",
        "l10n_br_stock_landed_costs",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizards/duimp_receipt_link_wizard_view.xml",
        "views/duimp_declaration_view.xml",
        "views/stock_landed_cost_view.xml",
    ],
    "installable": True,
}
