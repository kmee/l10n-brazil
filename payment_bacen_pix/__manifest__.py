# Copyright 2022 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Payment Bacen PIX",
    "summary": """Payment PIX with bacen""",
    "version": "12.0.2.0.0",
    "license": "AGPL-3",
    "author": "KMEE, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "depends": [
        "payment",
        "l10n_br_account_payment_order"
    ],
    "data": [
        "views/payment_transfer_templates.xml",
        "data/payment_icon_data.xml",
        "data/payment_acquirer_data.xml",
        "views/payment_views.xml",
        "data/ir_cron_data.xml",
    ],
    "demo": [],
}
