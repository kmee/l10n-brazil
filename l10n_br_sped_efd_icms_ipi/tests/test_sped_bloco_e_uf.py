# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from odoo.addons.l10n_br_tax_assessment.tests.common_entrada import SpedEntradaCommon

from .test_sped_entrada import EntradaHelpers


@tagged("post_install", "-at_install")
class TestSpedEfdIcmsIpiBlocoEUf(EntradaHelpers, SpedEntradaCommon):
    """E200 and E300 for each state of the 0015, which the Guia Pratico makes
    mandatory even without movement (the PVA: "E200 obrigatório" and "E300
    deve ser informado para a UF")."""

    def _substitute_in(self, state):
        self.env["state.tax.numbers"].create(
            {
                "partner_id": self.company.partner_id.id,
                "state_id": state.id,
                "l10n_br_ie_code": "86.817.30-6",
            }
        )

    def _lines(self, declaration, register):
        return [
            line
            for line in declaration._generate_sped_text().splitlines()
            if line.startswith(f"|{register}|")
        ]

    def test_e200_and_e300_without_movement_for_the_state_of_the_0015(self):
        self._entry_document()
        self._substitute_in(self.env.ref("base.state_br_rj"))
        declaration = self._declaration_july()
        period = {"DT_INI": "01072026", "DT_FIN": "31072026"}
        self.assertEqual(
            self._sped_records(declaration, "E200"), [{"UF": "RJ", **period}]
        )
        self.assertEqual(
            self._sped_records(declaration, "E300"), [{"UF": "RJ", **period}]
        )
        # without movement every value is written, as zero
        self.assertEqual(
            self._lines(declaration, "E210"), ["|E210|0" + "|0" * 13 + "|"]
        )
        self.assertEqual(
            self._lines(declaration, "E310"), ["|E310|0" + "|0" * 20 + "|"]
        )
        declaration._check_assessments_by_state()

    def test_no_e200_nor_e300_without_0015(self):
        self._entry_document()
        declaration = self._declaration_july()
        self.assertEqual(self._lines(declaration, "E200"), [])
        self.assertEqual(self._lines(declaration, "E300"), [])

    def test_a_state_of_the_0015_with_st_is_not_written_with_zeros(self):
        """The assessment has no state: with ST for the state of the 0015 the
        E210 cannot be read, and the file stops instead of going out empty."""
        state = self.env.ref("base.state_br_rj")
        self.partner_a.state_id = state
        self._entry_document(line_vals={"icmsst_base": 100.0, "icmsst_value": 18.0})
        self._substitute_in(state)
        declaration = self._declaration_july()
        self.assertEqual(self._lines(declaration, "E200"), [])
        with self.assertRaises(UserError):
            declaration._check_assessments_by_state()

    def test_a_state_of_the_0015_with_difal_is_not_written_with_zeros(self):
        state = self.env.ref("base.state_br_rj")
        self.partner_a.state_id = state
        self._entry_document(line_vals={"icms_destination_value": 5.0})
        self._substitute_in(state)
        declaration = self._declaration_july()
        self.assertEqual(self._lines(declaration, "E300"), [])
        with self.assertRaises(UserError):
            declaration._check_assessments_by_state()
