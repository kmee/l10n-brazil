# Copyright 2026 KMEE (Ygor Carvalho <ygor.carvalho@kmee.com.br>)
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestCancelAnswers(TransactionCase):
    """Pressing cancel on a document the SEFAZ never authorized.

    It used to answer nothing at all: the method fell through both branches and
    returned None, so the button did nothing and said nothing, and whoever
    pressed it could not tell a cancellation from a broken screen.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.document = cls.env["l10n_br_fiscal.document"].create(
            {
                "document_type_id": cls.env.ref("l10n_br_fiscal.document_55").id,
                "document_serie_id": cls.env.ref(
                    "l10n_br_fiscal.document_55_serie_1"
                ).id,
                "fiscal_operation_type": "out",
            }
        )

    def test_a_document_never_authorized_says_why_it_cannot_be_cancelled(self):
        self.assertNotEqual(self.document.state_edoc, "autorizada")
        with self.assertRaises(UserError):
            self.document._action_document_cancel()

    def test_the_message_points_at_invalidating_the_number(self):
        """The number the document took is given back by invalidation, and the
        message has to say so, or the operator keeps pressing cancel."""
        try:
            self.document._action_document_cancel()
        except UserError as erro:
            self.assertIn("invalidate", str(erro).lower())
        else:
            raise AssertionError("cancelling a document never authorized should refuse")
