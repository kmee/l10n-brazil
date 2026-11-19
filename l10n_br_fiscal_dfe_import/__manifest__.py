# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Fiscal Document Import by File or Access Key",
    "summary": "Import NF-e XML files or an access key straight into a draft "
    "fiscal document",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "development_status": "Beta",
    "category": "Localisation",
    "author": "KMEE, Odoo Community Association (OCA)",
    "maintainers": ["mileo"],
    "website": "https://github.com/OCA/l10n-brazil",
    "depends": ["l10n_br_fiscal_dfe", "l10n_br_nfe_dfe"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/document_import_dfe_wizard.xml",
        "views/document_view.xml",
        "views/document_import_menu.xml",
    ],
    "uninstall_hook": "uninstall_hook",
}
