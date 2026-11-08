# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models

# Fields of the item reference of return NF-e (det/DFeReferenciado) that
# l10n_br_nfe adds to the fiscal line mixin form. They only exist on the fiscal
# document line (and on the models that delegate to it, like the invoice line).
REF_DOCUMENT_FIELDS = ("ref_document_related_id", "ref_document_item")


class FiscalDocumentLineMixin(models.AbstractModel):
    _inherit = "l10n_br_fiscal.document.line.mixin"

    @api.model
    def inject_fiscal_fields(self, doc, *args, **kwargs):
        """The fiscal line mixin form is also injected into the views of
        models that only inherit the mixin (purchase.order.line, stock.move,
        sale.order.line...). They do not have the item reference fields, so
        drop them (and their group) from the injected nodes."""
        doc = super().inject_fiscal_fields(doc, *args, **kwargs)
        if all(fname in self._fields for fname in REF_DOCUMENT_FIELDS):
            return doc
        field_names = " or ".join(f"@name='{fname}'" for fname in REF_DOCUMENT_FIELDS)
        for node in doc.xpath(
            f"//group[@name='ref_document'] | //field[{field_names}]"
        ):
            if node.getparent() is not None:
                node.getparent().remove(node)
        return doc
