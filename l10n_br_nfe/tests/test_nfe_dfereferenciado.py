# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64

from lxml import etree

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_br_fiscal.tests.tools import get_undefined_view_fields

KEY_1 = "35200159594315000157550010000000032062777166"
KEY_2 = "35200159594315000157550010000000022062777169"
KEY_OTHER_ISSUER = "35200681583054000129550010000000012760018057"


@tagged("post_install", "-at_install")
class TestNFeDFeReferenciado(TransactionCase):
    """Test the item references (det/DFeReferenciado) of return NF-e
    (NT 2025.002, VC02-14)"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.ref("base.main_company")
        cls.nfe_type = cls.env.ref("l10n_br_fiscal.document_55")
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "is_company": True,
                "vat": "65910976000147",
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Test Product", "default_code": "TEST001"}
        )

    def _create_document(self, fiscal_operation):
        return self.env["l10n_br_fiscal.document"].create(
            {
                "company_id": self.company.id,
                "partner_id": self.partner.id,
                "fiscal_operation_type": fiscal_operation.fiscal_operation_type,
                "fiscal_operation_id": fiscal_operation.id,
                "document_type_id": self.nfe_type.id,
            }
        )

    def _create_return(self):
        return self._create_document(
            self.env.ref("l10n_br_fiscal.fo_devolucao_compras")
        )

    def _add_related(self, document, key):
        return self.env["l10n_br_fiscal.document.related"].create(
            {
                "document_id": document.id,
                "document_type_id": self.nfe_type.id,
                "document_key": key,
            }
        )

    def _add_line(self, document, **extra_vals):
        vals = {
            "document_id": document.id,
            "product_id": self.product.id,
            "quantity": 1.0,
            "price_unit": 100.0,
        }
        vals.update(extra_vals)
        return self.env["l10n_br_fiscal.document.line"].create(vals)

    def _export_dfe_ref(self, line):
        return line.with_context(
            spec_schema="nfe", spec_version="40"
        )._export_m2o_via_tag_hooks("nfe40_DFeReferenciado", self.env["nfe.40.det"])

    def _export_nfref(self, document):
        return document.with_context(
            spec_schema="nfe", spec_version="40"
        )._export_one2many("nfe40_NFref", self.env["nfe.40.ide"])

    def test_export_single_related_document(self):
        """With one related document the line only sets the item number"""
        document = self._create_return()
        self._add_related(document, KEY_1)
        line = self._add_line(document, ref_document_item=3)

        dfe_ref = self._export_dfe_ref(line)
        self.assertEqual(dfe_ref.chaveAcesso, KEY_1)
        self.assertEqual(dfe_ref.nItem, "3")

    def test_export_line_related_document(self):
        """With several related documents the line chooses one"""
        document = self._create_return()
        self._add_related(document, KEY_1)
        related_2 = self._add_related(document, KEY_2)
        line = self._add_line(
            document, ref_document_related_id=related_2.id, ref_document_item=1
        )

        dfe_ref = self._export_dfe_ref(line)
        self.assertEqual(dfe_ref.chaveAcesso, KEY_2)
        self.assertEqual(dfe_ref.nItem, "1")

    def test_export_ambiguous_related_document(self):
        """Several related documents and none chosen: no group exported"""
        document = self._create_return()
        self._add_related(document, KEY_1)
        self._add_related(document, KEY_2)
        line = self._add_line(document, ref_document_item=1)

        self.assertFalse(self._export_dfe_ref(line))

    def test_export_not_return(self):
        """Other purposes keep NFref and never export the group"""
        document = self._create_document(self.env.ref("l10n_br_fiscal.fo_venda"))
        self._add_related(document, KEY_1)
        line = self._add_line(document, ref_document_item=3)

        self.assertFalse(self._export_dfe_ref(line))
        self.assertEqual(len(self._export_nfref(document)), 1)

    def test_export_return_without_nfref(self):
        """Return NF-e does not export NFref (VC02-05)"""
        document = self._create_return()
        self._add_related(document, KEY_1)
        self._add_line(document, ref_document_item=3)

        self.assertEqual(self._export_nfref(document), [])
        self.assertTrue(document.document_related_ids)

    def test_check_valid_references(self):
        document = self._create_return()
        self._add_related(document, KEY_1)
        related_2 = self._add_related(document, KEY_2)
        related_1 = document.document_related_ids - related_2
        self._add_line(
            document, ref_document_related_id=related_1.id, ref_document_item=1
        )
        self._add_line(
            document, ref_document_related_id=related_2.id, ref_document_item=1
        )

        document._check_nfe_item_references()

    def test_check_missing_item(self):
        document = self._create_return()
        self._add_related(document, KEY_1)
        self._add_line(document)

        with self.assertRaisesRegex(UserError, "referenced item number"):
            document._check_nfe_item_references()

    def test_check_missing_related_document(self):
        document = self._create_return()
        self._add_line(document, ref_document_item=1)

        with self.assertRaisesRegex(UserError, "set the referenced document"):
            document._check_nfe_item_references()

    def test_check_duplicated_reference(self):
        document = self._create_return()
        self._add_related(document, KEY_1)
        self._add_line(document, ref_document_item=2)
        self._add_line(document, ref_document_item=2)

        with self.assertRaisesRegex(UserError, "already referenced"):
            document._check_nfe_item_references()

    def test_check_different_issuers(self):
        document = self._create_return()
        related_1 = self._add_related(document, KEY_1)
        related_2 = self._add_related(document, KEY_OTHER_ISSUER)
        self._add_line(
            document, ref_document_related_id=related_1.id, ref_document_item=1
        )
        self._add_line(
            document, ref_document_related_id=related_2.id, ref_document_item=1
        )

        with self.assertRaisesRegex(UserError, "same issuer"):
            document._check_nfe_item_references()

    def test_check_not_return(self):
        """Other purposes are not checked"""
        document = self._create_document(self.env.ref("l10n_br_fiscal.fo_venda"))
        self._add_line(document)

        document._check_nfe_item_references()

    def test_return_nfe_xml(self):
        """The XML of a return NF-e carries det/DFeReferenciado with the
        original key and item number on every item, no NFref, and passes
        the NF-e 4.00 XSD validation"""
        company = self.env.ref("l10n_br_base.empresa_lucro_presumido")
        self.env.user.company_ids += company
        self.env.user.company_id = company
        partner = self.env.ref("l10n_br_base.res_partner_cliente7_rs")
        operation = self.env.ref("l10n_br_fiscal.fo_devolucao_compras")
        document = self.env["l10n_br_fiscal.document"].create(
            {
                "company_id": company.id,
                "partner_id": partner.id,
                "document_type_id": self.nfe_type.id,
                "fiscal_operation_id": operation.id,
                "fiscal_operation_type": operation.fiscal_operation_type,
                "ind_final": "0",
            }
        )
        self._add_related(document, KEY_1)
        for item, product in (
            (2, self.env.ref("product.product_product_4c")),
            (5, self.env.ref("product.product_product_4c")),
        ):
            self.env["l10n_br_fiscal.document.line"].create(
                {
                    "document_id": document.id,
                    "company_id": company.id,
                    "partner_id": partner.id,
                    "fiscal_operation_type": operation.fiscal_operation_type,
                    "fiscal_operation_id": operation.id,
                    "product_id": product.id,
                    "quantity": 1.0,
                    "price_unit": 100.0,
                    "ref_document_item": item,
                }
            )
        self.assertEqual(document.edoc_purpose, "4")

        document.action_document_confirm()

        xml = base64.b64decode(document.send_file_id.datas)
        root = etree.fromstring(xml)
        ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
        self.assertEqual(
            root.xpath("//nfe:ide/nfe:finNFe/text()", namespaces=ns), ["4"]
        )
        self.assertFalse(root.xpath("//nfe:NFref", namespaces=ns))
        dets = root.xpath("//nfe:det", namespaces=ns)
        self.assertEqual(len(dets), 2)
        refs = [
            (
                det.xpath("nfe:DFeReferenciado/nfe:chaveAcesso/text()", namespaces=ns),
                det.xpath("nfe:DFeReferenciado/nfe:nItem/text()", namespaces=ns),
            )
            for det in dets
        ]
        self.assertEqual(refs, [([KEY_1], ["2"]), ([KEY_1], ["5"])])
        self.assertFalse(document.xml_error_message)

    def test_mixin_form_injection(self):
        """The item reference fields come with the fiscal line mixin form,
        which is injected into the views of every model inheriting the mixin
        (purchase.order.line, stock.move...): they must only be kept for the
        models that have them."""
        placeholder = (
            "<form><group name='fiscal_fields' invisible='1'/>"
            "<notebook><page name='fiscal_line_extra_info'/></notebook></form>"
        )
        line_model = self.env["l10n_br_fiscal.document.line"]
        arch = line_model.inject_fiscal_fields(etree.fromstring(placeholder))
        self.assertTrue(arch.xpath("//field[@name='ref_document_item']"))
        self.assertTrue(arch.xpath("//group[@name='ref_document']"))

        # the abstract mixin itself does not have the fields, like the
        # business lines that only inherit it
        mixin = self.env["l10n_br_fiscal.document.line.mixin"]
        self.assertNotIn("ref_document_item", mixin._fields)
        arch = mixin.inject_fiscal_fields(etree.fromstring(placeholder))
        self.assertTrue(arch.xpath("//field[@name='fiscal_operation_id']"))
        self.assertFalse(arch.xpath("//field[@name='ref_document_item']"))
        self.assertFalse(arch.xpath("//field[@name='ref_document_related_id']"))
        self.assertFalse(arch.xpath("//group[@name='ref_document']"))

    def test_mixin_form_fields_defined(self):
        """Every field of the fiscal line mixin form exists on the fiscal
        document line, the model of the view"""
        arch, _view = self.env["l10n_br_fiscal.document.line"]._get_view(
            view_type="form"
        )
        self.assertFalse(
            get_undefined_view_fields(self.env, "l10n_br_fiscal.document.line", arch)
        )
