# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, models


class FiscalDocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    def copy_data(self, default=None):
        res = super().copy_data(default)
        if self.env.context.get("mirror_copy"):
            tax_fields = [
                name
                for name, field in self._fields.items()
                if field.store and field.compute == "_compute_tax_fields"
            ]
            for line, vals in zip(self, res, strict=True):
                for name in tax_fields:
                    if name not in vals:
                        vals[name] = line._fields[name].convert_to_write(
                            line[name], line
                        )
                vals["fiscal_tax_ids"] = [Command.set(line.fiscal_tax_ids.ids)]
        return res
