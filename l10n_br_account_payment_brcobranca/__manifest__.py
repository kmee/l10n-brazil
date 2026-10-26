# Copyright 2017 Akretion
# @author Raphaël Valyi <raphael.valyi@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Boletos e CNAB de cobrança",
    "summary": "receivable Boletos and CNAB using the BRCobranca lib",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Akretion, Odoo Community Association (OCA)",
    "maintainers": ["rvalyi", "mbcosta"],
    "website": "https://github.com/OCA/l10n-brazil",
    "depends": [
        "l10n_br_account_payment_order",
        "account_move_base_import",
    ],
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Views
        "views/account_journal_view.xml",
        # Wizard
        "wizard/import_statement_view.xml",
    ],
    "demo": [
        "demo/account_journal_demo.xml",
        "demo/account_move_demo.xml",
        "demo/account_payment_mode.xml",
    ],
    "external_dependencies": {
        "python": [
            # Pino afrouxado de proposito nesta branch, para o Grupo Prevencao.
            # O modulo usa UMA funcao da biblioteca, misc.punctuation_rm, e ela
            # existe na 2.3.1, que e a versao pinada no pip.txt da imagem
            # erplivre-odoo. O pino original, >=2.4.2, e conservador e nao
            # tecnico: nada do que o modulo chama mudou entre as duas versoes.
            # Rodando assim na homologacao do cliente desde 06/10/2026.
            # Tirar este desvio quando a imagem subir o erpbrasil-base.
            "erpbrasil-base>=2.3.1",
        ]
    },
}
