# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """The ICMS SN of the generic chart gets the accounts of the ICMS.

    The generic chart had no account for the tax group of the ICMS SN, so the
    credit that a Simples Nacional supplier passes went to the cost account of
    the product line instead of the ICMS to recover. The data now carries it for
    new companies; the companies that already have the chart get the accounts
    of the ICMS of the same company and kind of tax, only where the repartition
    line has none, so an account the user chose is never overwritten.
    """
    template = env.ref("l10n_br_coa_generic.l10n_br_coa_generic_template")
    group_sn = env.ref("l10n_br_coa.tax_group_icmssn")
    group_icms = env.ref("l10n_br_coa.tax_group_icms")
    taxes = env["account.tax"].search(
        [
            ("tax_group_id", "=", group_sn.id),
            ("company_id.chart_template_id", "=", template.id),
        ]
    )
    for tax in taxes:
        model = env["account.tax"].search(
            [
                ("tax_group_id", "=", group_icms.id),
                ("company_id", "=", tax.company_id.id),
                ("type_tax_use", "=", tax.type_tax_use),
                ("deductible", "=", tax.deductible),
                ("no_credit", "=", tax.no_credit),
                ("withholdable", "=", tax.withholdable),
            ],
            limit=1,
        )
        if not model:
            continue
        for field in ("invoice_repartition_line_ids", "refund_repartition_line_ids"):
            model_line = model[field].filtered(
                lambda line: line.repartition_type == "tax"
            )[:1]
            for line in tax[field].filtered(
                lambda line: line.repartition_type == "tax" and not line.account_id
            ):
                if model_line.account_id:
                    line.account_id = model_line.account_id
