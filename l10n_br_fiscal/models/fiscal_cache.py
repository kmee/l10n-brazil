# Copyright (C) 2026 KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
"""Transaction-scoped caches for the fiscal engine.

The Brazilian fiscal engine maps and computes taxes many times per document
line within a single save (the onchange/compute cascade re-runs the mapping
and the tax computation with the *same* inputs several times per line). These
helpers provide a cache whose lifetime is exactly one database transaction, so
those redundant re-executions collapse into a single one — without ever
leaking results between transactions or workers.

Anchoring
---------
The cache dict is stored as an attribute on the *cursor* (``env.cr``). A cursor
lives for exactly one transaction: every web request / job gets a fresh cursor
(hence a fresh, empty cache), and there is one cursor per worker at a time, so
nothing is shared between transactions or across workers. This is deliberately
NOT a module-level dict (which would leak across transactions and workers).

Invalidation
------------
Mapping/computation results are a pure function of the input record ids **and**
the fiscal *definition* tables (tax definitions, ICMS regulation, taxes, tax
classifications). The cache keys already encode every input record id plus the
scalar configuration fields that drive the mapping branches (tax framework,
``ind_ie_dest``, ICMS origin, states...), so a change to any *keyed* value
naturally produces a different key.

What the keys do NOT observe is an in-place edit of a *definition* table row
(e.g. changing a tax rate or a tax-definition applicability) while keeping the
same id. ``FiscalCacheMixin`` covers exactly that: any create/write/unlink on a
definition model that inherits it wipes the whole transaction cache, so a
definition edited mid-transaction (config screens, tests) forces a recompute.

Known, documented limitation: an in-place edit of a *non-definition* config
field that feeds the mapping but is not in the key (e.g. ``ncm.tax_ipi_id``)
during the very same transaction that already mapped a line is not observed.
This does not happen in the supported document flows (fiscal configuration is
not mutated in the middle of computing a line's taxes).
"""

from odoo import api, models

_TXN_CACHE_ATTR = "_l10n_br_fiscal_txn_cache"


def get_fiscal_txn_cache(env, name):
    """Return the (create-on-demand) transaction-scoped cache dict ``name``."""
    cr = env.cr
    store = getattr(cr, _TXN_CACHE_ATTR, None)
    if store is None:
        store = {}
        setattr(cr, _TXN_CACHE_ATTR, store)
    return store.setdefault(name, {})


def clear_fiscal_txn_cache(env):
    """Drop every transaction-scoped fiscal cache of the current cursor."""
    cr = env.cr
    if getattr(cr, _TXN_CACHE_ATTR, None):
        setattr(cr, _TXN_CACHE_ATTR, None)


class FiscalCacheMixin(models.AbstractModel):
    """Wipe the transaction fiscal caches on any change of a definition model.

    Inherited by the fiscal *definition* models whose rows feed the mapping and
    the tax computation. Kept intentionally tiny: it only clears the caches; the
    per-key correctness is handled by the cache keys themselves.
    """

    _name = "l10n_br_fiscal.cache.mixin"
    _description = "Fiscal transaction cache invalidation"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        clear_fiscal_txn_cache(self.env)
        return records

    def write(self, vals):
        res = super().write(vals)
        clear_fiscal_txn_cache(self.env)
        return res

    def unlink(self):
        res = super().unlink()
        clear_fiscal_txn_cache(self.env)
        return res
