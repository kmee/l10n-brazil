from odoo import _, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    iface_tef = fields.Boolean(
        related="pos_config_id.iface_tef", readonly=False
    )

    institution_selection = fields.Selection(
        related="pos_config_id.institution_selection", readonly=False
    )

    environment_selection = fields.Selection(
        related="pos_config_id.environment_selection", readonly=False
    )
