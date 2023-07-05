# Copyright 2020 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Payment PagSeguro",
    "summary": """Payment Acquirer: PagSeguro  Implementation""",
    "version": "12.0.2.0.1",
    "license": "AGPL-3",
    "author": "KMEE, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "depends": [
        "sale",  # Used sale order in currency validation
        "web_tour",
        "l10n_br_base",
        "l10n_br_account_payment_order",  # Used for Boleto Payment form
    ],
    "data": [
        "views/payment_pagseguro_templates.xml",
        "data/payment_acquirer_data.xml",
        "data/payment_method_data.xml",
        "data/payment_mode.xml",
        "data/ir_cron_data.xml",        
        "views/payment_acquirer.xml",
        "views/sale_order.xml",
    ],
    "demo": [],
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {
        "python": [
            "erpbrasil.base",
        ],
    },
}
