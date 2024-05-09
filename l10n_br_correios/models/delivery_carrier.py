from odoo import _, api, fields, models
from odoo.exceptions import UserError

class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"
    
    delivery_type = fields.Selection(
        selection_add=[("correios", "Correios")],
        ondelete={"correios": "set default"},
    )
    
    correios_user = fields.Char(string="Usuário do Portal")
    correios_password = fields.Char(string="Código de acesso a API")