import importlib.util

# A suite herda o cenario de valorizacao liquida do PR #4739, que nasceu sobre
# o #4733 (l10n_br_stock_account/tests/test_stock_valuation.py). Nesta branch de
# integracao o #4733 ficou de fora porque reescreve o mesmo _get_price_unit que
# o #4744 reescreve, entao o case base pode nao existir: sem esta guarda o
# ImportError derruba a carga do registro inteiro com --test-enable.
if importlib.util.find_spec(
    "odoo.addons.l10n_br_stock_account.tests.test_stock_valuation"
):
    from . import test_landed_cost  # noqa: F401
