# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    """The lines of a document imported by the old wizard have no review state.

    The wizard was the review: its grid chose the product, the unit and the factor
    before the document existed. The documents it left are reviewed already, so
    their lines are resolved, and the invoice of one that has none yet can be
    generated from the new screen, which only accepts resolved lines.

    Only lines without a state of imported documents are touched, so what a person
    is still reviewing is left alone and the migration can run again. The state of
    the document is stored, and the pre-migration created its column empty, so the
    documents left with all the lines resolved get their state here too.
    """
    cr.execute(
        """
        UPDATE l10n_br_fiscal_document_line line
           SET import_state = 'resolved'
          FROM l10n_br_fiscal_document document
         WHERE line.document_id = document.id
           AND document.imported_document
           AND line.import_state IS NULL
        """
    )
    cr.execute(
        """
        UPDATE l10n_br_fiscal_document document
           SET import_state = 'resolved'
         WHERE document.imported_document
           AND document.import_state IS NULL
           AND NOT EXISTS (
                SELECT 1
                  FROM l10n_br_fiscal_document_line line
                 WHERE line.document_id = document.id
                   AND line.import_state IS DISTINCT FROM 'resolved'
           )
        """
    )
