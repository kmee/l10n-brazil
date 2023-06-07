from __future__ import division, print_function, unicode_literals

from odoo import _, fields, models
from odoo.exceptions import Warning as UserError


class MdfeCancelamentoWizard(models.TransientModel):
    _name = 'mdfe.cancellation.wizard'

    cancellation_reason = fields.Char(
        string='Justificativa para Cancelamento de NF-e',
        required=True,
    )

    def action_cancellation_reason(self):
        """

        :return:
        """

        self.ensure_one()

        if len(self.cancellation_reason) < 10:
            raise UserError(_('A justificativa deve ter mais de 10 caracteres.'))

        mdfe = self.env['l10n_br_fiscal.document'].browse(self.env.context['active_id'])

        mdfe.justificativa = self.cancellation_reason

        mdfe.cancelar_documento()

        return {'type': 'ir.actions.act_window_close'}
