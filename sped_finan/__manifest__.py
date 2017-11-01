# -*- coding: utf-8 -*-
# Copyright 2017 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Sped Financeiro',
    'summary': """
        Integracão entre o controle financeiro e o módulo fiscal""",
    'version': '11.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'KMEE,Odoo Community Association (OCA)',
    'website': 'www.odoobrasil.org.br',
    'depends': [
        'finan',
        'sped',
    ],
    'data': [
        'views/inherited_sped_operacao_base_view.xml',
        'views/inherited_sped_documento_base_view.xml',
    ],
    'demo': [
    ],
    'installable': True,
}
