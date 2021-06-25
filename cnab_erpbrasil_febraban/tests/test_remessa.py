# Copyright 2021 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase
import base64


class TestRemessa(TransactionCase):

    def setUp(self):
        super().setUp()

        self.invoice_itau240_charge = self.env.ref(
            'l10n_br_account_payment_order.demo_invoice_payment_order_itau_cnab240'
        )

    def test_remessa_itau240_charge(self):
        """ Test CNAB 240 charge remittance to Itau bank """
        self.invoice_itau240_charge.payment_mode_id.service_type = '01'
        self.invoice_itau240_charge.payment_term_id = self.env.ref('account.account_payment_term_immediate').id
        self.invoice_itau240_charge.partner_id = self.env.ref('l10n_br_base.res_partner_kmee').id
        self.invoice_itau240_charge.action_invoice_open()

        payment_order = self.env['account.payment.order'].search([
            ('payment_mode_id', '=', self.invoice_itau240_charge.payment_mode_id.id),
            ('state', '=', 'draft')
        ])

        payment_order.draft2open()
        payment_order.open2generated()
        self.assertEqual(len(payment_order.bank_line_ids), 1)

        attachment_id = self.env['ir.attachment'].search([
            ('name', '=', payment_order.name + '.REM'),
        ])
        self.assertEqual(len(attachment_id), 1)
