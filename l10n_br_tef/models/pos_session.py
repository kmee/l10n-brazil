from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_pos_payment_method(self):

        result = super()._loader_params_pos_payment_method()
        result["search_params"]["fields"].extend(
            ["vspague_payment_terminal_mode", "vspague_product_type"]
        )

        return result
