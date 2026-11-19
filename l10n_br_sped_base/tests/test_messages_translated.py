# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

import ast
import glob
import os

import polib

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

# Modules whose messages are written in English in the code and translated in
# the pt_BR file. The l10n_br_tax_assessment writes its messages in Portuguese
# in the code itself, so it has no translation file to check.
MODULES = (
    "l10n_br_sped_base",
    "l10n_br_sped_efd_icms_ipi",
    "l10n_br_sped_efd_pis_cofins",
)


def _messages_of_the_code(module_path):
    """The msgid of every `_("...")` of the Python code of the module (not of the
    tests, the migrations or the generated layouts)."""
    messages = {}
    for path in glob.glob(os.path.join(module_path, "**", "*.py"), recursive=True):
        if any(part in path for part in ("/tests/", "/migrations/", "_spec_")):
            continue
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                messages[node.args[0].value] = os.path.relpath(path, module_path)
    return messages


@tagged("post_install", "-at_install")
class TestMessagesAreTranslated(TransactionCase):
    """Every message the code of the SPED modules shows to the user has a
    translation to Brazilian Portuguese: a message that is not in the .po (or
    whose text no longer matches the code, after a change of wording) comes out
    in English for a user in pt_BR."""

    def test_every_msgid_of_the_code_has_a_pt_br_translation(self):
        missing = []
        checked = 0
        for module in MODULES:
            module_path = get_module_path(module)
            po_path = module_path and os.path.join(module_path, "i18n", "pt_BR.po")
            if not po_path or not os.path.exists(po_path):
                continue
            translated = {
                entry.msgid: entry.msgstr
                for entry in polib.pofile(po_path)
                if entry.msgstr
            }
            for msgid, where in _messages_of_the_code(module_path).items():
                checked += 1
                if not translated.get(msgid):
                    missing.append(f"{where}: {msgid[:80]}")
        self.assertTrue(checked, "no message was found in the code")
        self.assertFalse(missing, "\n".join(missing))
