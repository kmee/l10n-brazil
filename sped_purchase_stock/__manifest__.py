# -*- coding: utf-8 -*-
# Copyright 2017 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Sped Compras',
    'summary': """
        Compras Brasileira""",
    'version': '11.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'KMEE,Odoo Community Association (OCA)',
    'website': 'www.kmee.com.br',
    'depends': [
        'sped_stock',
        'sped_purchase',
    ],
    'data': [
        'views/stock_picking.xml',
    ],
    'demo': [
    ],
    'installable': True,
}
