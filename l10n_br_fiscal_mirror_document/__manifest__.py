# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Brazilian Localization Fiscal Mirror Document",
    "summary": "Copy an imported fiscal document to a company document without"
    " recomputing taxes and set the payment mode on documents without invoice",
    "category": "Localization",
    "license": "AGPL-3",
    "author": "KMEE, Odoo Community Association (OCA)",
    "maintainers": ["mileo"],
    "website": "https://github.com/OCA/l10n-brazil",
    "version": "18.0.1.0.0",
    "development_status": "Beta",
    "depends": [
        "l10n_br_account_nfe",
    ],
    "data": [
        "views/document_view.xml",
    ],
    "demo": [
        "demo/fiscal_document_demo.xml",
    ],
}
