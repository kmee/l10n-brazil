# Copyright 2020 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class PaymentTokenPagSeguro(models.Model):
    _inherit = "payment.token"

    pagseguro_card_holder_name = fields.Char(
        string="Pagseguro Card Holder"
    )

    pagseguro_card_brand = fields.Char(string="Pagseguro Card Brand")

    pagseguro_card_token = fields.Char(string="Pagseguro Card Token")

    pagseguro_payment_method = fields.Char(string="Pagseguro Payment Method")

    pagseguro_installments = fields.Integer(string="Pagseguro Number of Installments")

    pagseguro_tx_id = fields.Char(string="Pagseguro PIX Transaction Id")

    @api.model
    def pagseguro_create(self, values):
        """Treats tokenizing data.
        Formats the response data to the result and returns a resulting dict
        containing card token, formated name (Customer Name or Card holder name)
        and partner_id will be returned.
        """

        partner_id = self.env["res.partner"].browse(values["partner_id"])

        if partner_id:
            description = "Partner: %s (id: %s)" % (partner_id.name, partner_id.id)
        else:
            description = values["cc_holder_name"]

        customer_params = {"description": description}

        res = {
            "acquirer_ref": partner_id.id,
            "name": "%s" % (customer_params.get("description")),
            "pagseguro_card_token": values.get("pagseguro_card_token"),
        }

        return res
