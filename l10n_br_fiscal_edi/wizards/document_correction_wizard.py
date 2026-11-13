# Copyright 2019 KMEE
# Copyright (C) 2020  Renato Lima - Akretion <renato.lima@akretion.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class DocumentCorrectionWizard(models.TransientModel):
    _name = "l10n_br_fiscal.document.correction.wizard"
    _description = "Fiscal Document Correction Wizard"
    _inherit = "l10n_br_fiscal.base.wizard.mixin"

    justification = fields.Text(
        required=True,
        help="NF-e: 15 to 1000 characters; line breaks, tabs, repeated spaces and "
        "typographic punctuation are normalized before sending.",
    )
    correction_sequence = fields.Integer(
        string="CC-e Sequence",
        compute="_compute_correction_sequence",
        readonly=False,
        store=True,
        help="Sequence number (nSeqEvento) of the correction letter. It is the "
        "next one after the letters known by Odoo. Change it when letters of "
        "this note were already issued outside Odoo (e.g. in the previous ERP): "
        "use the number after the last one issued.",
    )

    @api.depends("document_id")
    def _compute_correction_sequence(self):
        for wizard in self:
            wizard.correction_sequence = (
                wizard.document_id._get_next_correction_sequence()
                if wizard.document_id
                else 1
            )

    def doit(self):
        action = None
        for wizard in self:
            if wizard.document_id:
                action = (
                    wizard.document_id.with_context(
                        correction_sequence=wizard.correction_sequence
                    )._document_correction(wizard.justification)
                    or action
                )
        return action or self._close()
