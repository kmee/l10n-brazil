# Copyright 2020 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'L10n Br Account Bank Statement Import Cnab',
    'summary': """
        Importação de Extrato Bancário CNAB 240 - Segmento E""",
    'version': '12.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'KMEE,Odoo Community Association (OCA)',
    'website': 'https://github.com/oca/l10n-brazil.git',
    'maintainers': ['mileo'],
    "development_status": "Alpha",
    'depends': [
        'account_bank_statement_import',
    ],
    'data': [
        'views/view_account_bank_statement_import.xml',
    ],
    'external_dependencies': {
        'python': ['febraban'],
    },
}
