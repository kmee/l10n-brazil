# Copyright 2026 KMEE (https://www.kmee.com.br)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Brazilian Localization NF-e Customer Product Code",
    "summary": "Customer product code and name (cProd/xProd) on the NF-e",
    "category": "Localisation",
    "license": "AGPL-3",
    "author": "KMEE, Odoo Community Association (OCA)",
    "maintainers": ["mileo"],
    "website": "https://github.com/OCA/l10n-brazil",
    "version": "18.0.1.0.0",
    "development_status": "Beta",
    "depends": [
        "l10n_br_nfe",
        "l10n_br_sale",
        "l10n_br_stock_account",
        "product_customerinfo",
    ],
    "data": [
        "views/document_line_mixin_view.xml",
    ],
    "demo": [
        "demo/product_customerinfo_demo.xml",
    ],
    "installable": True,
}
