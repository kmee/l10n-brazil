# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Fiscal Document Import: Invoicing",
    "summary": "Generate the vendor bill of an imported fiscal document",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "development_status": "Beta",
    "category": "Localisation",
    "author": "KMEE, Odoo Community Association (OCA)",
    "maintainers": ["mileo"],
    "website": "https://github.com/OCA/l10n-brazil",
    "depends": ["l10n_br_account", "l10n_br_fiscal_dfe_import"],
    "data": ["views/document_view.xml"],
    "auto_install": True,
}
