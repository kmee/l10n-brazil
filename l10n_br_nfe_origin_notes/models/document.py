# Copyright 2026 KMEE (https://www.kmee.com.br)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class Document(models.Model):
    _inherit = "l10n_br_fiscal.document"

    add_origin_nfe_to_xml = fields.Boolean(
        string="Add Origin Notes to the NF-e",
        compute="_compute_add_origin_nfe_to_xml",
        store=True,
        readonly=False,
    )

    origin_nfes_numbers = fields.Char(
        string="Origin Notes Numbers",
        compute="_compute_origin_nfes_numbers",
        store=True,
        readonly=False,
        copy=False,
        help="Numbers of the related documents, separated by comma.",
    )

    @api.depends("fiscal_operation_id.add_origin_nfe_to_xml")
    def _compute_add_origin_nfe_to_xml(self):
        for document in self:
            document.add_origin_nfe_to_xml = (
                document.fiscal_operation_id.add_origin_nfe_to_xml
            )

    @api.depends(
        "document_related_ids.document_number",
        "document_related_ids.document_related_id.document_number",
    )
    def _compute_origin_nfes_numbers(self):
        for document in self:
            numbers = []
            for related in document.document_related_ids:
                number = (
                    related.document_number
                    or related.document_related_id.document_number
                    or ""
                ).lstrip("0")
                if number and number not in numbers:
                    numbers.append(number)
            document.origin_nfes_numbers = ",".join(numbers)

    def _document_comment(self):
        result = super()._document_comment()
        for document in self:
            if document.add_origin_nfe_to_xml and document.origin_nfes_numbers:
                text = " ".join(
                    filter(
                        None,
                        [
                            document.fiscal_operation_id.origin_nfes_text,
                            document.origin_nfes_numbers,
                        ],
                    )
                )
                document.customer_additional_data = " - ".join(
                    filter(None, [document.customer_additional_data, text])
                )
        return result
