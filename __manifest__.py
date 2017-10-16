# -*- coding: utf-8 -*-
# Copyright 2016 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'eSocial - Brasil',
    'summary': """
        Implementa todos os ajustes necessários ao Odoo para suportar os 
        serviços do eSocial brasileiro.
        """,
    'version': '11.0.1.0.0',
    'category': 'Hidden',
    'license': 'AGPL-3',
    'author': 'KMEE,Odoo Community Association (OCA)',
    'website': 'www.odoobrasil.org.br',
    'depends': [
        'l10n_br_base',
    ],
    'external_dependencies': {
        'python': [
            'pybrasil',
        ],
    },
    'data': [
        'views/menus.xml',
        'views/categoria_trabalhador.xml',
        'views/financiamento_aposentadoria.xml',
        'views/natureza_rubrica.xml',
        'views/parte_corpo.xml',
        'views/agente_causador.xml',
        'views/situacao_geradora_doenca.xml',
        'views/situacao_geradora_acidente.xml',
        'views/natureza_lesao.xml',
        'views/motivo_afastamento.xml',
        'views/motivo_desligamento.xml',
        'views/tipo_logradouro.xml',
        'views/natureza_juridica.xml',
        'views/motivo_cessacao.xml',
        'views/tipo_beneficio.xml',
        'data/natureza_lesao.xml',
        'data/categoria_trabalhador.xml',
        'data/financiamento_aposentadoria.xml',
        'data/natureza_rubrica.xml',
        'data/parte_corpo.xml',
        'data/agente_causador.xml',
        'data/situacao_geradora_doenca.xml',
        'data/situacao_geradora_acidente.xml',
        'data/natureza_lesao.xml',
        'data/motivo_afastamento.xml',
        'data/motivo_desligamento.xml',
        'data/tipo_logradouro.xml',
        'data/natureza_juridica.xml',
        'data/motivo_cessacao.xml',
        'data/tipo_beneficio.xml',
    ],
    'application': True,
}
