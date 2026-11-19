# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """The regime of a PIS/COFINS assessment follows the company when the tax
    group does not say it: the assessments that were left with "not applicable"
    get the regime recomputed."""
    assessments = env["l10n_br_tax.assessment"].search(
        [("regime", "=", "not_applicable"), ("tax_domain", "in", ("pis", "cofins"))]
    )
    env.add_to_compute(env["l10n_br_tax.assessment"]._fields["regime"], assessments)
