# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Brazilian Localization Sale Customer Reference",
    "summary": "Customer order reference and sale order on the fiscal document"
    " and the invoice",
    "category": "Localization",
    "license": "AGPL-3",
    "author": "KMEE, Odoo Community Association (OCA)",
    "maintainers": ["mileo"],
    "website": "https://github.com/OCA/l10n-brazil",
    "version": "18.0.1.0.0",
    "development_status": "Beta",
    "depends": [
        "l10n_br_sale_stock",
        "sale_order_line_client_order_ref",
    ],
    "data": [
        "views/document_view.xml",
        "views/account_move_view.xml",
    ],
    "demo": [
        "demo/l10n_br_fiscal_comment_demo.xml",
        "demo/sale_order_demo.xml",
    ],
}
