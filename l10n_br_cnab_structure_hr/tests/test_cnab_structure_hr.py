# Copyright 2026 KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo.tests.common import tagged

from odoo.addons.l10n_br_cnab_structure.tests import test_cnab_structure as base_tests

SVC_SALARY = base_tests.SVC_SALARY
SVC_SUPPLIER = base_tests.SVC_SUPPLIER


@tagged("post_install", "-at_install")
class TestCNABStructureHR(base_tests.TestCNABStructure):
    """Employee detection through hr.employee.work_contact_id.

    Inherits the base test case only for its fixtures; the inherited tests are
    disabled below so they are not run twice.
    """

    def _create_hr_employee(self, partner):
        return self.env["hr.employee"].create(
            {
                "name": "Employee Test",
                "work_contact_id": partner.id,
                "company_id": self.company.id,
            }
        )

    def test_employee_by_work_contact(self):
        """hr.employee work contact is an employee even with the flag off."""
        rule = self._create_employee_rule()
        self.assertFalse(self.partner_a.employee)
        self._create_hr_employee(self.partner_a)
        self.assertFalse(self.partner_a.employee)
        invoice = self._create_test_invoice()
        order = self._create_payment_order(invoice)
        line = order.payment_line_ids
        self.assertTrue(line._is_cnab_employee())
        self.assertEqual(line._get_matching_rule(), rule)
        self.assertEqual(line.service_type, SVC_SALARY)

    def test_employee_created_after_line_recomputes(self):
        """Creating the hr.employee after the line recalculates it (draft)."""
        self._create_employee_rule()
        invoice = self._create_test_invoice()
        order = self._create_payment_order(invoice)
        line = order.payment_line_ids
        self.assertEqual(line.service_type, SVC_SUPPLIER)
        self._create_hr_employee(self.partner_a)
        self.assertEqual(line.service_type, SVC_SALARY)

    def test_exported_order_not_changed_by_hr_employee(self):
        """An exported order keeps its service type when an employee appears."""
        self._create_employee_rule()
        invoice = self._create_test_invoice()
        order = self._create_payment_order(invoice)
        line = order.payment_line_ids
        order.draft2open()
        order.open2generated()
        self._create_hr_employee(self.partner_a)
        line._compute_cnab_payment_way_id()
        self.assertEqual(line.service_type, SVC_SUPPLIER)

    def test_partner_without_employee_is_supplier(self):
        invoice = self._create_test_invoice()
        order = self._create_payment_order(invoice)
        self.assertFalse(order.payment_line_ids._is_cnab_employee())


# Fixtures only: do not run the base test methods again in this module.
for _name in [n for n in dir(base_tests.TestCNABStructure) if n.startswith("test_")]:
    if _name not in TestCNABStructureHR.__dict__:
        setattr(TestCNABStructureHR, _name, None)
