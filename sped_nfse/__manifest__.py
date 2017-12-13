# -*- coding: utf-8 -*-
# Copyright 2017 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Sped Nfse',
    'summary': """
        Transmissão de NFS-E""",
    'version': '10.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'KMEE,Odoo Community Association (OCA)',
    'website': 'www.kmee.com.br',
    'depends': [
        'sped_nfe',
    ],
    'installable': True,
    'application': False,
    'data': [
        'views/sped_documento_item.xml',
        'views/inherited_sped_documento_emissao_nfse_view.xml',
    ],
    'demo': [
    ],
    'external_dependencies': {
        'python': [
             'pytrustnfe',
        ],
    },
}
