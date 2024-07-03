# Copyright (C) 2024 Diego Paradeda - KMEE <diego.paradeda@kmee.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models
from odoo.tools.float_utils import float_round


class StockPriceMixin(models.AbstractModel):
    _name = "l10n_br_stock_account.stock.price.mixin"
    _description = "Stock Price Mixin"

    def _default_valuation_stock_price(self):
        """
        Método para chavear o custo médio dos produtos entre:
        - líquido de impostos
        - com impostos (padrão do Odoo).
        TODO: Posicionar o campo para o usuário poder interagir com esse chaveamento
            a nível de company
        """
        return True

    valuation_via_stock_price = fields.Boolean(
        string="Valuation Via Stock Price",
        default=_default_valuation_stock_price,
        help="Determina se o valor utilizado no custeamento automático será padrão do"
        " Odoo ou com base no campo stock_price_br.\n\n"
        "    * Usar True para valor de estoque líquido (sem imposto)",
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        default=lambda self: self.env.ref("base.BRL"),
    )

    stock_price_br = fields.Monetary(
        string="Stock Price", compute="_compute_stock_price_br"
    )

    @api.depends("amount_total", "fiscal_tax_ids", "valuation_via_stock_price")
    def _compute_stock_price_br(self):
        """Subtract creditable taxes from stock price."""
        for record in self:
            record.stock_price_br = 0

            if not hasattr(record, "product_uom_qty"):
                continue

            if record.fiscal_operation_line_id and record.product_uom_qty:
                price = record.amount_total

                if not record.valuation_via_stock_price:
                    continue

                for tax in record.fiscal_tax_ids:
                    if hasattr(record, "%s_tax_id" % (tax.tax_domain,)):
                        tax_id = getattr(record, "%s_tax_id" % (tax.tax_domain,))
                        if tax_id and tax_id.creditable_tax:
                            if not hasattr(record, "%s_value" % (tax.tax_domain)):
                                continue
                            price -= getattr(record, "%s_value" % (tax.tax_domain))

                price_precision = self.env["decimal.precision"].precision_get(
                    "Product Price"
                )
                record.stock_price_br = float_round(
                    (price / record.product_uom_qty), precision_digits=price_precision
                )
