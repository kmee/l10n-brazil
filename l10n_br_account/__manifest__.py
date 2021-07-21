# Copyright (C) 2009 - TODAY Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

{
    "name": "Brazilian Localization Account",
    "category": "Localisation",
    "license": "AGPL-3",
    "author": "Akretion, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "version": "12.0.7.0.0",
    "depends": ["account_cancel", "l10n_br_coa", "l10n_br_fiscal"],
    "data": [
        # security
        "security/ir.model.access.csv",
        # data
        "data/account_tax_group.xml",
        "data/account_tax_template.xml",
        # Views
        "views/res_partner_view.xml",
        "views/account_tax_view.xml",
        "views/account_tax_template_view.xml",
        "views/fiscal_operation_view.xml",
        "views/fiscal_operation_line_view.xml",
        "views/account_invoice_view.xml",
        "views/account_invoice_line_view.xml",
        "views/document_line_view.xml",
        "views/document_view.xml",
        "views/fiscal_invoice_view.xml",
        "views/fiscal_invoice_line_view.xml",
        "views/l10n_br_fiscal_cfop.xml",
        # Wizards
        "wizards/account_invoice_refund_view.xml",
        "wizards/wizard_document_status.xml",
        # Actions
        "views/l10n_br_account_action.xml",
        # Menus
        "views/l10n_br_account_menu.xml",
        # Report
        "report/account_invoice_report_view.xml",
    ],
    "demo": [
        "demo/res_users_demo.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
}
