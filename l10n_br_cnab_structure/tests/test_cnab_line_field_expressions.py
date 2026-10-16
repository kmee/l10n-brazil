# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestCnabLineFieldExpressions(TransactionCase):
    def test_dynamic_content_expressions_compile(self):
        """All dynamic content expressions shipped as data must be valid Python."""
        fields_with_expr = self.env["l10n_br_cnab.line.field"].search(
            [
                "|",
                ("sending_dynamic_content", "!=", False),
                ("return_dynamic_content", "!=", False),
            ]
        )
        self.assertTrue(fields_with_expr)
        for field in fields_with_expr:
            for fname in ("sending_dynamic_content", "return_dynamic_content"):
                expr = field[fname]
                if not expr:
                    continue
                try:
                    compile(expr.strip(), field.display_name, "eval")
                except SyntaxError as e:
                    self.fail(f"Invalid {fname} on {field.display_name}: {e}")

    def test_expression_keys_exist_in_layout(self):
        """Keys read by the expressions must be ref_names of the same batch."""
        key_re = re.compile(
            r"""(?:get|startswith)\(\s*["'](\d+_\d+_[^"']*)["']"""
            r"""|\[\s*["'](\d+_\d+_[^"']*)["']\s*\]"""
        )
        names_by_scope = {}
        for fld in self.env["l10n_br_cnab.line.field"].search([]):
            line = fld.cnab_line_id
            scope = (line.cnab_structure_id.id, line.batch_id.id)
            names_by_scope.setdefault(scope, set()).add(fld.ref_name)
        checked = 0
        errors = []
        fields_with_expr = self.env["l10n_br_cnab.line.field"].search(
            [
                "|",
                ("sending_dynamic_content", "!=", False),
                ("return_dynamic_content", "!=", False),
            ]
        )
        for field in fields_with_expr:
            line = field.cnab_line_id
            scope = (line.cnab_structure_id.id, line.batch_id.id)
            expr = (field.sending_dynamic_content or "") + (
                field.return_dynamic_content or ""
            )
            for match in key_re.finditer(expr):
                key = match.group(1) or match.group(2)
                checked += 1
                if "startswith" in match.group(0):
                    found = any(n.startswith(key) for n in names_by_scope[scope])
                else:
                    found = key in names_by_scope[scope]
                if not found:
                    errors.append(
                        f"{field.display_name} ({line.cnab_structure_id.name}) "
                        f"reads the key '{key}' missing in its batch layout"
                    )
        self.assertTrue(checked)
        self.assertFalse(errors, "\n".join(errors))
