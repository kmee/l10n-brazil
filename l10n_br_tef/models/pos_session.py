from odoo import _, fields, models


class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_pos_payment_method(self):

        result = super()._loader_params_pos_payment_method()
        result['search_params']['fields'].extend(
            ['destaxa_payment_terminal_mode', 'destaxa_product_type']
        )

        return result
