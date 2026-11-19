# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).


def migrate(cr, version):
    """A company that already assessed by the system starts in the month of its
    earliest assessment. A company that never did stays empty: the assessment asks
    for the date (an existing base must not be asked for its whole history)."""
    cr.execute(
        """
        UPDATE res_company company
           SET tax_assessment_start = first.month
          FROM (
                SELECT company_id,
                       date_trunc('month', min(date_from))::date AS month
                  FROM l10n_br_tax_assessment
                 WHERE state = 'posted'
                 GROUP BY company_id
               ) first
         WHERE first.company_id = company.id
           AND company.tax_assessment_start IS NULL
        """
    )
