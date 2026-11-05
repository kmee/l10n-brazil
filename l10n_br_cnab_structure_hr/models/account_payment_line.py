# Copyright 2026 KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, models


class AccountPaymentLine(models.Model):
    _inherit = "account.payment.line"

    def _is_cnab_employee(self):
        """Also treat the work contact of an hr.employee as an employee.

        In Odoo 18 the hr module does not compute res.partner.employee, so the
        flag is never set by registering the employee in HR. employee_ids is the
        inverse of hr.employee.work_contact_id and is restricted to HR users,
        hence the sudo().
        """
        self.ensure_one()
        return super()._is_cnab_employee() or bool(self.partner_id.sudo().employee_ids)

    @api.depends("partner_id.employee_ids")
    def _compute_cnab_payment_way_id(self):
        """Add employee_ids to the dependencies of the base compute."""
        return super()._compute_cnab_payment_way_id()
