from odoo import _, fields, models

WA03_CMP_MP = [
    ("01", "Cartão Crédito"),
    ("02", "Cartão Débito"),
]


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    def _get_payment_terminal_selection(self):
        res = super()._get_payment_terminal_selection()
        res.append(("vspague_payment_terminal", _("VSPague Payment Terminal")))
        return res

    vspague_payment_terminal_mode = fields.Selection(
        [("Credito", "Cartão Crédito"), ("Debito", "Cartão Débito")],
        string="Payment Mode",
        default="Credito",
    )

    vspague_product_type = fields.Selection(
        [
            # ("CDC-Userede", "CDC-Userede"),
            # ("Consulta AVS-Userede", "Consulta AVS-Userede"),
            ("Crediario-Userede", "Crediario-Userede"),
            ("Credito-Safrapay", "Credito-Safrapay"),
            ("Credito-Userede", "Credito-Userede"),
            ("Debito-Safrapay", "Debito-Safrapay"),
            ("Debito-Userede", "Debito-Userede"),
            ("PIX-Shipay", "PIX-Shipay"),
            ("Picpay-Shipay", "Picpay-Shipay"),
            ("Voucher Frota-Userede", "Voucher Frota-Userede"),
            ("Voucher-Safrapay", "Voucher-Safrapay"),
            ("Voucher-Userede", "Voucher-Userede"),
        ]
    )
