# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import os
import re
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase

from odoo.addons import l10n_br_nfe

FIXTURE_DIR = os.path.join(
    l10n_br_nfe.__path__[0], "tests", "nfe", "v4_00", "leiauteNFe"
)
FIXTURE_DEST = re.compile(rb"(<dest>\s*)<(?:CNPJ|CPF)>\d+</(?:CNPJ|CPF)>")
KEY_1 = "35200159594315000157550010000000012062777161"
KEY_2 = "35200159594315000157550010000000022062777169"


class DfeImportCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.other_company = cls.env.ref("l10n_br_base.empresa_lucro_real")
        cls.Document = cls.env["l10n_br_fiscal.document"]

    @classmethod
    def _xml(cls, key, recipient=None, product="Brand new thing"):
        with open(os.path.join(FIXTURE_DIR, f"NFe{key}.xml"), "rb") as xml_file:
            content = xml_file.read()
        recipient = recipient or cls.company.partner_id.cnpj_cpf_stripped
        content = FIXTURE_DEST.sub(rb"\1<CNPJ>%s</CNPJ>" % recipient.encode(), content)
        content = content.replace(b"Cabinet with Doors", product.encode())
        return content.replace(b"E-COM11", b"ZZ-NEW-1")

    def _imported(self, key, company=None):
        return self.Document.search(
            [
                ("document_key", "=", key),
                ("company_id", "=", (company or self.company).id),
                ("imported_document", "=", True),
            ]
        )

    def _dfe_document(self, key, summary_only=True, days=0):
        dfe_document = self.env["l10n_br_fiscal_dfe.document"].create(
            {
                "access_key": key,
                "company_id": self.company.id,
                "fiscal_type": "nfe",
                "document_state": "1",
                "document_emission_date": fields.Datetime.now() - timedelta(days=days),
            }
        )
        dfe = self.env["l10n_br_fiscal_dfe.dfe"].create(
            {
                "access_key": key,
                "company_id": self.company.id,
                "fiscal_type": "nfe",
                "dfe_document_id": dfe_document.id,
                "document_type_dfe": "summary" if summary_only else "complete",
            }
        )
        if not summary_only:
            dfe.create_xml_attachment(self._xml(key))
        return dfe_document
