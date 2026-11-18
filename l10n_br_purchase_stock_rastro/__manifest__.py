# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Brazilian Localization Purchase Stock Rastro",
    "summary": "Propose the lots and expiry dates of the NF-e on the receipt",
    "license": "AGPL-3",
    "category": "Localisation",
    "author": "KMEE, Odoo Community Association (OCA)",
    "maintainers": ["mileo"],
    "website": "https://github.com/OCA/l10n-brazil",
    "version": "16.0.1.0.0",
    "development_status": "Alpha",
    "depends": [
        "l10n_br_nfe",
        "l10n_br_purchase_stock",
        "product_expiry",
    ],
    "data": [
        "views/stock_picking_view.xml",
    ],
    "installable": True,
}
