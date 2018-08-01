# -*- coding: utf-8 -*-
# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'L10n Br Fiscal Financial',
    'summary': """
        Link entre o módulo financeiro e o fiscal""",
    'version': '8.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'KMEE INFORMATICA LTDA,Odoo Community Association (OCA)',
    'website': 'www.kmee.com.br',
    'depends': [
        'l10n_br_account_product',
        'financial_account',
    ],
    'data': [
        'security/ir.model.access.csv',

        # 'views/l10n_br_account_fiscal_category.xml',
        # 'views/account_invoice_nfe_view.xml',
        # 'views/financial_move.xml',
        # 'views/sped_forma_pagamento_view.xml',
    ],
    'demo': [
        # 'demo/l10n_br_account_fiscal_category.xml',
    ],
    'auto_install': True,
}
