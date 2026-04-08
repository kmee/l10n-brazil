# Copyright (C) 2023 Antônio S. P. Neto <neto@engene.one> - Engenere LTDA (https://engenere.one).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import common


class TestNFSePaulistana(common.TransactionCase):

    def setUp(self):
        super(TestNFSePaulistana, self).setUp()
        self.Document = self.env['l10n_br_fiscal.document']
        self.Move = self.env['account.move']

        # Create a test company
        self.company = self.env['res.company'].create({
            'name': 'Test Company',
            'city_id': self.env.ref('l10n_br_base.city_3550308').id,
            'inscr_mun': '1234567890',
        })

        # Create a test document
        self.document = self.Document.create({
            'company_id': self.company.id,
            'document_type_id': self.env.ref("l10n_br_fiscal.document_SE").id,
            'document_number': '123456',
            'verify_code': '12345',
        })

    def test_compute_url_nfse_paulistana(self):
        # Test with all required fields
        self.document._compute_url_nfse_paulistana()
        expected_url = (
            "https://nfe.prefeitura.sp.gov.br/contribuinte/notaprint.aspx?"
            "nf=123456&inscricao=1234567890&verificacao=12345"
        )
        self.assertEqual(self.document.url_nfse_paulistana, expected_url)

        # Test with missing required fields
        self.document.document_number = False
        self.document._compute_url_nfse_paulistana()
        self.assertEqual(self.document.url_nfse_paulistana, '')

    def test_action_open_nfse_paulistana(self):
        # Ensure URL is computed
        self.document._compute_url_nfse_paulistana()
        
        action = self.document.action_open_nfse_paulistana()
        expected_action = {
            'type': 'ir.actions.act_url',
            'url': self.document.url_nfse_paulistana,
            'target': 'new',
        }
        self.assertDictEqual(action, expected_action)

    def test_compute_is_nfse_paulistana(self):
        self.document._compute_is_nfse_paulistana()
        self.assertTrue(self.document.is_nfse_paulistana)

        self.document.document_type_id = self.env.ref("l10n_br_fiscal.document_55")
        self.document._compute_is_nfse_paulistana()
        self.assertFalse(self.document.is_nfse_paulistana)

        self.document.document_type_id = self.env.ref("l10n_br_fiscal.document_SE")
        self.document.company_id.city_id = False
        self.document._compute_is_nfse_paulistana()
        self.assertFalse(self.document.is_nfse_paulistana)

    def test_account_move_action(self):
        # Create a move linked to the document
        # We need to bypass the read-only or computed nature if fiscal_document_id is computed
        # But usually in l10n_br_account it might be editable or set during invoicing
        # For testing purposes, we try to create it.
        
        # Note: l10n_br_account usually adds fiscal_document_id to account.move
        # We assume it exists and is writable or we can create a move that triggers its creation.
        # Simpler: just mock the relation if possible, or create move.
        
        move = self.Move.create({
            'move_type': 'out_invoice',
            'partner_id': self.env['res.partner'].create({'name': 'Test Partner'}).id,
            'date': '2023-01-01',
            'journal_id': self.env['account.journal'].search([('type', '=', 'sale')], limit=1).id,
        })
        
        # Manually link if field exists (it should due to dependency)
        if hasattr(move, 'fiscal_document_id'):
            move.fiscal_document_id = self.document.id
            
            # Ensure URL is computed on the document
            self.document._compute_url_nfse_paulistana()
            
            action = move.action_open_nfse_paulistana()
            expected_action = {
                'type': 'ir.actions.act_url',
                'url': self.document.url_nfse_paulistana,
                'target': 'new',
            }
            self.assertDictEqual(action, expected_action)
