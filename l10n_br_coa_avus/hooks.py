# Copyright 2023 - TODAY, Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def _post_init_hook(env):
    company = env.ref(
        "l10n_br_base.empresa_lucro_presumido", raise_if_not_found=False
    )
    if company:
        env["account.chart.template"].try_loading(
            "br_oca_avus", company, install_demo=True
        )
