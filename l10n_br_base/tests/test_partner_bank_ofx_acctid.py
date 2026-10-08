# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import unittest

from odoo.tests import TransactionCase

OFX_TEMPLATE = """<?xml version="1.0" encoding="ASCII"?>
<?OFX OFXHEADER="200" VERSION="211" SECURITY="NONE"?>
<OFX>
  <SIGNONMSGSRSV1>
    <SONRS>
      <STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS>
      <DTSERVER>20261007120000</DTSERVER>
      <LANGUAGE>POR</LANGUAGE>
    </SONRS>
  </SIGNONMSGSRSV1>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <TRNUID>0</TRNUID>
      <STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS>
      <STMTRS>
        <CURDEF>BRL</CURDEF>
        <BANKACCTFROM>
          <BANKID>0341</BANKID>
          <ACCTID>5118005031</ACCTID>
          <ACCTTYPE>CHECKING</ACCTTYPE>
        </BANKACCTFROM>
        <BANKTRANLIST>
          <DTSTART>20261001</DTSTART>
          <DTEND>20261007</DTEND>
          <STMTTRN>
            <TRNTYPE>CREDIT</TRNTYPE>
            <DTPOSTED>20261005120000</DTPOSTED>
            <TRNAMT>100.00</TRNAMT>
            <FITID>20261005001</FITID>
            <NAME>Test</NAME>
          </STMTTRN>
        </BANKTRANLIST>
        <LEDGERBAL><BALAMT>100.00</BALAMT><DTASOF>20261007</DTASOF></LEDGERBAL>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
"""


class PartnerBankOfxAcctidTest(TransactionCase):
    """Itau OFX ACCTID 5118005031 matches a clean 5118 / 00503 / 1 account."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "acctid" not in cls.env["res.partner.bank"]._fields:
            raise unittest.SkipTest(
                "account_statement_import_ofx_by_acctid is not installed"
            )
        cls.brl = cls.env.ref("base.BRL")
        cls.env.company.currency_id = cls.brl
        cls.bank = cls.env["res.partner.bank"].create(
            {
                "partner_id": cls.env.company.partner_id.id,
                "company_id": cls.env.company.id,
                "bra_number": "5118",
                "acc_number": "00503",
                "acc_number_dig": "1",
                "acctid": "5118005031",
            }
        )
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Itau OFX acctid",
                "code": "ITAU9",
                "type": "bank",
                "bank_account_id": cls.bank.id,
            }
        )
        cls.other_journal = cls.env["account.journal"].create(
            {"name": "Other bank", "code": "OTH9", "type": "bank"}
        )
        cls.wizard = cls.env["account.statement.import"].create(
            {
                "statement_file": base64.b64encode(OFX_TEMPLATE.encode()),
                "statement_filename": "itau.ofx",
            }
        )

    def test_match_without_journal_in_context(self):
        journal = self.wizard._match_journal("5118005031", self.brl)
        self.assertEqual(journal, self.journal)

    def test_match_with_journal_in_context(self):
        wizard = self.wizard.with_context(journal_id=self.journal.id)
        self.assertEqual(wizard._match_journal("5118005031", self.brl), self.journal)
