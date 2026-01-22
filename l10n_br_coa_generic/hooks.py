# Copyright (C) 2020 - Gabriel Cardoso de Faria <gabriel.cardoso@kmee.com.br>
# Copyright (C) 2024 - Ravi do Valle Luz <raviluz@xipptech.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import tools


def _post_init_hook(env):
    # Load COA for demo Company
    company_lc = env.ref(
        "l10n_br_base.empresa_lucro_presumido", raise_if_not_found=False
    )
    if company_lc:
        # Use install_demo=True to avoid warning about registry not being fully loaded
        # This is appropriate since we're loading demo data for a demo company.
        # The install_demo flag suppresses the warning and is correct for demo data.
        chart_template = env["account.chart.template"]
        chart_template.try_loading("br_oca_generic", company_lc, install_demo=True)
        tools.convert_file(
            env,
            "l10n_br_coa_generic",
            "demo/account_journal.xml",
            None,
            mode="init",
            noupdate=True,
            kind="init",
        )
