# Copyright (C) 2022 Marcel Savegnago - Escodoo
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html


def _post_init_hook(env):
    company = env.ref(
        "l10n_br_base.empresa_lucro_presumido", raise_if_not_found=False
    )
    if company:
        env["account.chart.template"].try_loading(
            "br_oca_ans", company, install_demo=True
        )
