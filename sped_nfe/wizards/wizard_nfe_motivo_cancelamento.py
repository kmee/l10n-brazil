from __future__ import division, print_function, unicode_literals

from odoo import api, fields, models, _
from odoo.exceptions import Warning as UserError


class FinanLancamento(models.TransientModel):
    _name = b'nfe.cancelamento.wizard'
    _inherit = 'sped.documento'

    motivo_cancelamento = fields.Char(
        string='Justificativa para Cancelamento de NF-e',
        required=True,
    )

    @api.multi
    def motivo_cancelamento_action(self):
        self.ensure_one()

        vals = {
            'justificativa':self.motivo_cancelamento,
        }

        nfe = self.env['sped.documento'].browse(
                self.env.context['active_id'])

        if len(self.motivo_cancelamento) > 10:
            nfe.justificativa = self.motivo_cancelamento

            # nfe.cancela_nfe()
        else:
            raise UserError("A justificativa deve ter mais de 10"
                              " caracteres.")

        return nfe
