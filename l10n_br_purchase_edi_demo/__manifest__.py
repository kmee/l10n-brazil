# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Fiscal Document EDI: Purchases Demo",
    "summary": "Demo data of the purchases and stock links of the import of "
    "fiscal documents, with sample NF-e files",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "development_status": "Beta",
    "category": "Localisation",
    "author": "KMEE, Odoo Community Association (OCA)",
    "maintainers": ["mileo"],
    "website": "https://github.com/OCA/l10n-brazil",
    "depends": [
        "l10n_br_nfe",
        "l10n_br_purchase_stock_edi",
    ],
    "demo": [
        "demo/purchase_edi_demo.xml",
        "demo/purchase_stock_edi_demo.xml",
    ],
    "auto_install": True,
}
