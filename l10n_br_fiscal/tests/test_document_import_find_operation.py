# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase


class TestDocumentImportFindOperation(TransactionCase):
    """Fiscal operation lookup of the document import wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.wizard = cls.env["l10n_br_fiscal.document.import.wizard"].create({})
        cls.cfop_5102 = cls.env.ref("l10n_br_fiscal.cfop_5102")
        cls.cfop_6102 = cls.env.ref("l10n_br_fiscal.cfop_6102")
        cls.cfop_1102 = cls.env.ref("l10n_br_fiscal.cfop_1102")
        cls.cfop_2102 = cls.env.ref("l10n_br_fiscal.cfop_2102")

    def _create_operation(self, name, operation_type, fiscal_type, cfops):
        operation = self.env["l10n_br_fiscal.operation"].create(
            {
                "code": name,
                "name": name,
                "fiscal_operation_type": operation_type,
                "fiscal_type": fiscal_type,
                "state": "approved",
            }
        )
        self.env["l10n_br_fiscal.operation.line"].create(
            dict(
                cfops,
                fiscal_operation_id=operation.id,
                name=name,
                state="approved",
            )
        )
        return operation

    def test_inbound_goes_through_the_inverse_cfop(self):
        """The supplier declares the outbound CFOP (6102), the operation line
        of the company references the inbound one (2102)."""
        operation = self._create_operation(
            "Compra importada (teste)",
            "in",
            "purchase",
            {
                "cfop_internal_id": self.cfop_1102.id,
                "cfop_external_id": self.cfop_2102.id,
            },
        )
        self.assertEqual(
            self.wizard._find_fiscal_operation(
                "6102", "Compra importada (teste)", "in"
            ),
            operation,
        )

    def test_outbound_uses_the_declared_cfop(self):
        operation = self._create_operation(
            "Venda importada (teste)",
            "out",
            "sale",
            {
                "cfop_internal_id": self.cfop_5102.id,
                "cfop_external_id": self.cfop_6102.id,
            },
        )
        self.assertEqual(
            self.wizard._find_fiscal_operation(
                "5102", "Venda importada (teste)", "out"
            ),
            operation,
        )

    def test_unknown_cfop_finds_nothing(self):
        self.assertFalse(self.wizard._find_fiscal_operation("0000", "x", "in"))
        self.assertFalse(self.wizard._find_fiscal_operation(False, "x", "out"))
