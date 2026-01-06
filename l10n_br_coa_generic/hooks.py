# Copyright (C) 2020 - Gabriel Cardoso de Faria <gabriel.cardoso@kmee.com.br>
# Copyright (C) 2024 - Ravi do Valle Luz <raviluz@xipptech.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import tools


def post_init_hook(env):
    # Load COA for demo Company
    br_demo_companies = [
        env.ref("l10n_br_base.empresa_simples_nacional"),
        env.ref("l10n_br_base.empresa_lucro_presumido"),
    ]
    for company in br_demo_companies:
        if company:
            # Use install_demo=True to avoid warning about registry not being fully
            # loaded
            # This is appropriate since we're loading demo data for a demo company.
            # The install_demo flag suppresses the warning and is correct for demo data.
            chart_template = env["account.chart.template"]
            chart_template.try_loading("br_oca_generic", company, install_demo=True)
            tools.convert_file(
                env,
                "l10n_br_coa_generic",
                "demo/account_journal.xml",
                None,
                mode="init",
                noupdate=True,
                kind="init",
            )
