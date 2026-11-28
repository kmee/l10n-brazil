# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Brazilian Localization Delivery NFe - Volumes by Lot",
    "summary": "NF-e volumes by lot and move line, with wizards to create and "
    "fill volumes and an optional lock when validating the delivery",
    "category": "Localisation",
    "license": "AGPL-3",
    "author": "KMEE, Odoo Community Association (OCA)",
    "maintainers": ["mileo"],
    "website": "https://github.com/OCA/l10n-brazil",
    "development_status": "Beta",
    "version": "18.0.1.0.0",
    "depends": [
        "l10n_br_delivery_nfe",
        "stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizards/stock_picking_vol_create_view.xml",
        "wizards/stock_picking_vol_add_view.xml",
        "views/stock_picking_type_view.xml",
        "views/stock_picking_view.xml",
        "views/stock_picking_vol_view.xml",
    ],
    "demo": [
        "demo/stock_picking_demo.xml",
    ],
}
