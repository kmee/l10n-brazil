# Copyright 2026 - TODAY, Escodoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""Remove view órfã do módulo herdada da versão 16.0.

A view ``view_account_invoice_filter_inherit`` existia em 16.0 e alterava
``<filter name="unpaid">`` da view base ``account.view_account_invoice_filter``.
No Odoo 18 o filter ``unpaid`` foi removido da view base, e a view herdada
foi removida do módulo — mas em bases que passaram por upgrade v14→v18 ela
fica órfã no banco e quebra ``get_view`` de ``account.move`` com::

    ValueError: Element '<filter name="unpaid">' cannot be located in parent view
"""


def migrate(cr, version):
    cr.execute(
        """
        DELETE FROM ir_ui_view
        WHERE id IN (
            SELECT v.id FROM ir_ui_view v
            JOIN ir_model_data m
              ON m.model = 'ir.ui.view' AND m.res_id = v.id
            WHERE m.module = 'l10n_br_account_payment_order'
              AND m.name = 'view_account_invoice_filter_inherit'
        )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE model = 'ir.ui.view'
          AND module = 'l10n_br_account_payment_order'
          AND name = 'view_account_invoice_filter_inherit'
        """
    )
