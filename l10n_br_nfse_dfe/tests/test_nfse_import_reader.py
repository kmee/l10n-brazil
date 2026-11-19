# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import importlib.util
import os

from odoo.exceptions import UserError
from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase

from odoo.addons.l10n_br_nfse_dfe.tests.test_nfse_dfe import (
    ACCESS_KEY,
    nfse_xml,
)
from odoo.addons.l10n_br_nfse_dfe.tests.test_nfse_import import _reform_nfse_xml

TAX_PREFIXES = ("issqn", "ibs", "cbs", "pis", "cofins", "irpj", "csll")
DOCUMENT_FIELDS = (
    "company_id",
    "partner_id",
    "issuer",
    "imported_document",
    "fiscal_operation_id",
    "fiscal_operation_type",
    "document_type_id",
    "document_key",
    "document_number",
    "document_serie",
    "document_date",
    "rps_number",
    "amount_tax_withholding",
)
XMLID_NAME = "field_res_company__nfse_import_product_id"


def _values(record, names):
    return {name: record[name] for name in names}


class TestNfseImportReader(TransactionCase):
    """The import wizard of the DF-e creates the NFS-e with the reader of
    l10n_br_nfse, and the field it used moved there."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.Document = cls.env["l10n_br_fiscal.document"]
        cls.Wizard = cls.env["l10n_br_fiscal.document.import.wizard"]

    def _wizard(self, content, **values):
        wizard = self.Wizard.create(
            dict(
                {"company_id": self.company.id, "file": base64.b64encode(content)},
                **values,
            )
        )
        wizard._onchange_file()
        return wizard

    def _line_field_names(self):
        fields = self.env["l10n_br_fiscal.document.line"]._fields
        names = ["name", "price_unit", "service_type_id", "nbs_id", "product_id"]
        names += ["issqn_fg_city_id", "fiscal_tax_ids", "tax_classification_id"]
        names += [
            name
            for name in fields
            if name.startswith(tuple(f"{prefix}_" for prefix in TAX_PREFIXES))
            and name.rsplit("_", 1)[-1]
            in ("value", "base", "percent", "id", "reduction")
            and fields[name].type != "one2many"
            and fields[name].store
        ]
        return names

    def _snapshot(self, document):
        names = self._line_field_names()
        return (
            _values(document, DOCUMENT_FIELDS),
            [_values(line, names) for line in document.fiscal_line_ids],
        )

    def test_the_wizard_creates_the_same_document_as_the_import_service(self):
        for content in (nfse_xml(retention="1"), nfse_xml(retention="2")):
            wizard = self._wizard(content)
            _binding, by_wizard = wizard._create_edoc_from_file()
            wizard_snapshot = self._snapshot(by_wizard)
            by_wizard.unlink()
            documents, errors, _warnings = self.Document.with_company(
                self.company
            )._edi_import_files([("a.xml", content)])
            self.assertFalse(errors)
            self.assertEqual(self._snapshot(documents), wizard_snapshot)
            documents.unlink()

    def test_the_wizard_keeps_the_withholdings_and_the_taxes_of_the_file(self):
        wizard = self._wizard(_reform_nfse_xml())
        _binding, document = wizard._create_edoc_from_file()
        line = document.fiscal_line_ids
        self.assertAlmostEqual(line.pis_wh_value, 25.44)
        self.assertAlmostEqual(line.irpj_wh_value, 58.71)
        self.assertAlmostEqual(line.csll_wh_value, 39.14)
        self.assertAlmostEqual(line.ibs_value, 2.5)
        self.assertEqual(document.issuer, "partner")
        self.assertTrue(document.original_xml_file_id)

    def test_what_the_wizard_chose_wins_over_the_defaults(self):
        product = self.env["product.product"].create(
            {"name": "Chosen service", "type": "service"}
        )
        default = self.env["product.product"].create(
            {"name": "Default service", "type": "service"}
        )
        self.company.nfse_import_product_id = default
        partner = self.env["res.partner"].create({"name": "Chosen provider"})
        default_operation = self.env.ref("l10n_br_fiscal.fo_compras")
        operation = self.env["l10n_br_fiscal.operation"].search(
            [
                ("fiscal_operation_type", "=", "in"),
                ("state", "=", "approved"),
                ("id", "!=", default_operation.id),
            ],
            limit=1,
        )
        self.assertTrue(operation)
        wizard = self._wizard(nfse_xml(), product_id=product.id)
        wizard.partner_id = partner
        wizard.fiscal_operation_id = operation
        _binding, document = wizard._create_edoc_from_file()
        self.assertEqual(document.fiscal_line_ids.product_id, product)
        self.assertEqual(document.partner_id, partner)
        self.assertEqual(document.fiscal_operation_id, operation)
        self.assertEqual(wizard.document_id, document)

    def test_the_wizard_records_the_partners_that_the_file_created(self):
        cnpj = "12345678000195"
        content = nfse_xml(provider_cnpj=cnpj, provider_name="Born from the file")
        wizard = self._wizard(content)
        _binding, document = wizard._create_edoc_from_file()
        self.assertEqual(document.partner_id.cnpj_cpf_stripped, cnpj)
        self.assertIn(document.partner_id.display_name, document.message_ids[0].body)

    def test_the_wizard_refuses_a_key_with_a_wrong_size(self):
        wizard = self._wizard(nfse_xml())
        wizard.file = base64.b64encode(
            nfse_xml().replace(ACCESS_KEY.encode(), b"7" * 49)
        )
        with self.assertRaisesRegex(UserError, "50-digit access key"):
            wizard._create_edoc_from_file()

    def _migration(self):
        path = os.path.join(
            get_module_path("l10n_br_nfse_dfe"),
            "migrations",
            "16.0.1.1.1",
            "pre-migration.py",
        )
        spec = importlib.util.spec_from_file_location("nfse_dfe_pre_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.migrate

    def _xmlid_modules(self):
        self.env.cr.execute(
            "SELECT module, res_id FROM ir_model_data "
            "WHERE model = 'ir.model.fields' AND name = %s ORDER BY module",
            (XMLID_NAME,),
        )
        return self.env.cr.fetchall()

    def _own_xmlid(self, module):
        """Give the field the xmlid that ``module`` would have created."""
        field = self.env["ir.model.fields"]._get(
            "res.company", "nfse_import_product_id"
        )
        self.env.cr.execute(
            "DELETE FROM ir_model_data WHERE model = 'ir.model.fields' AND name = %s",
            (XMLID_NAME,),
        )
        for owner in module:
            self.env.cr.execute(
                "INSERT INTO ir_model_data (module, name, model, res_id, noupdate) "
                "VALUES (%s, %s, 'ir.model.fields', %s, false)",
                (owner, XMLID_NAME, field.id),
            )
        return field.id

    def test_the_xmlid_of_the_field_goes_to_l10n_br_nfse(self):
        field_id = self._own_xmlid(["l10n_br_nfse_dfe"])
        self._migration()(self.env.cr, "16.0.1.1.0")
        self.assertEqual(self._xmlid_modules(), [("l10n_br_nfse", field_id)])

    def test_the_xmlid_of_the_dfe_is_dropped_when_the_nfse_has_its_own(self):
        field_id = self._own_xmlid(["l10n_br_nfse", "l10n_br_nfse_dfe"])
        self._migration()(self.env.cr, "16.0.1.1.0")
        self.assertEqual(self._xmlid_modules(), [("l10n_br_nfse", field_id)])

    def test_the_migration_runs_twice_with_the_same_result(self):
        for owners in (["l10n_br_nfse_dfe"], ["l10n_br_nfse", "l10n_br_nfse_dfe"]):
            field_id = self._own_xmlid(owners)
            migrate = self._migration()
            migrate(self.env.cr, "16.0.1.1.0")
            migrate(self.env.cr, "16.0.1.1.0")
            self.assertEqual(self._xmlid_modules(), [("l10n_br_nfse", field_id)])
