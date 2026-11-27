# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Fiscal Document Import: Purchases and Stock",
    "summary": "Receipt as the origin of an imported fiscal document, lots "
    "declared by the document and divergence from the order and the receipt",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "development_status": "Beta",
    "category": "Localisation",
    "author": "KMEE, Odoo Community Association (OCA)",
    "maintainers": ["mileo"],
    "website": "https://github.com/OCA/l10n-brazil",
    "depends": [
        "l10n_br_purchase_stock",
        "l10n_br_purchase_edi",
    ],
    "data": [
        "views/res_company_view.xml",
        "views/document_view.xml",
        "views/document_match_view.xml",
        "views/account_move_view.xml",
        "views/stock_picking_view.xml",
    ],
    "post_init_hook": "post_init_hook",
    "auto_install": True,
}
