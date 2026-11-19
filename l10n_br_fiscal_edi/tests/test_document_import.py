# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import io
import zipfile
from unittest.mock import patch

from odoo.exceptions import UserError

from ..tools import EDI_IMPORT_NO_CREATE
from .common import KEY_1, KEY_2, KEY_3, EdiImportCase


def _zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files:
            archive.writestr(name, content)
    return buffer.getvalue()


class TestDocumentImport(EdiImportCase):
    """The service of import, with a reader that finds what the test tells it to."""

    def _import(self, files, parsed=(), model=None, **create_values):
        """Run ``_edi_import_files`` with a reader that recognizes the parsed files
        by their name and a creator that builds the draft document."""
        by_name = {parsed_file.file_name: parsed_file for parsed_file in parsed}
        test = self
        created = []

        def read(model_, name, content):
            return by_name.get(name)

        def create(model_, parsed_file, company, role):
            created.append(model_.env.context.get(EDI_IMPORT_NO_CREATE))
            return test._create_imported_document(
                company=company,
                model=model_,
                document_key=parsed_file.access_key,
                **create_values,
            )

        document_model = type(self.Document)
        with patch.object(document_model, "_edi_import_read", read), patch.object(
            document_model, "_edi_import_create", create
        ):
            result = (self.Document if model is None else model)._edi_import_files(
                files
            )
        self.create_contexts = created
        return result

    def test_a_file_is_imported_and_the_creation_never_creates_registries(self):
        parsed = self._parsed(KEY_1)
        documents, errors, warnings = self._import([(parsed.file_name, b"x")], [parsed])
        self.assertEqual((len(documents), errors, warnings), (1, [], []))
        self.assertEqual(self.create_contexts, [True])
        self.assertTrue(documents.imported_document)
        self.assertEqual(documents.document_key, KEY_1)

    def test_the_same_note_twice_opens_the_same_document_with_a_warning(self):
        parsed = self._parsed(KEY_1)
        files = [(parsed.file_name, b"x"), (parsed.file_name, b"x")]
        documents, errors, warnings = self._import(files, [parsed])
        self.assertEqual(len(documents), 1)
        self.assertFalse(errors)
        self.assertEqual([name for name, _msg in warnings], [parsed.file_name])
        self.assertEqual(self.Document.search_count([("document_key", "=", KEY_1)]), 1)

    def test_an_error_in_one_file_does_not_drop_the_batch(self):
        good, other = self._parsed(KEY_1), self._parsed(KEY_2)
        files = [
            (good.file_name, b"x"),
            ("garbage.xml", b"not a fiscal file"),
            (other.file_name, b"x"),
        ]
        documents, errors, _warnings = self._import(files, [good, other])
        self.assertEqual(len(documents), 2)
        self.assertEqual([name for name, _msg in errors], ["garbage.xml"])
        self.assertIn("not a fiscal document", errors[0][1])

    def test_a_zip_stands_for_the_files_it_holds(self):
        good, other = self._parsed(KEY_1), self._parsed(KEY_2)
        archive = _zip(
            [
                ("dir/", b""),
                ("__MACOSX/._" + good.file_name, b"metadata"),
                (good.file_name, b"x"),
                (other.file_name, b"x"),
            ]
        )
        names = [
            name
            for name, _content in self.Document._edi_import_expand(
                [("all.zip", archive)]
            )
        ]
        self.assertEqual(
            names, [f"all.zip/{good.file_name}", f"all.zip/{other.file_name}"]
        )

    def test_zip_with_two_notes_and_an_invalid_file(self):
        good, other = self._parsed(KEY_1), self._parsed(KEY_2)
        archive = _zip(
            [(good.file_name, b"x"), ("bad.xml", b"x"), (other.file_name, b"x")]
        )
        by_zip_name = [
            self._parsed(KEY_1, file_name=f"all.zip/{good.file_name}"),
            self._parsed(KEY_2, file_name=f"all.zip/{other.file_name}"),
        ]
        documents, errors, _warnings = self._import([("all.zip", archive)], by_zip_name)
        self.assertEqual(len(documents), 2)
        self.assertEqual([name for name, _msg in errors], ["all.zip/bad.xml"])

    def test_an_unexpected_error_is_reported_without_the_raw_message(self):
        parsed = self._parsed(KEY_1)
        with patch.object(
            type(self.Document), "_edi_import_read", side_effect=ValueError("secret")
        ):
            documents, errors, _warnings = self.Document._edi_import_files(
                [(parsed.file_name, b"x")]
            )
        self.assertFalse(documents)
        self.assertNotIn("secret", errors[0][1])
        self.assertIn("unexpected error", errors[0][1])

    def test_a_cancelled_or_denied_note_is_refused(self):
        for status, text in (("cancelled", "cancelled"), ("denied", "denied")):
            parsed = self._parsed(KEY_1, status=status)
            documents, errors, _warnings = self._import(
                [(parsed.file_name, b"x")], [parsed]
            )
            self.assertFalse(documents)
            self.assertIn(text, errors[0][1])
        self.assertFalse(self.Document.search([("document_key", "=", KEY_1)]))

    def test_a_company_outside_the_switcher_is_refused_before_creating(self):
        parsed = self._parsed(KEY_1, company=self.other_company)
        model = self.Document.with_context(allowed_company_ids=self.company.ids)
        documents, errors, _warnings = self._import(
            [(parsed.file_name, b"x")], [parsed], model=model
        )
        self.assertFalse(documents)
        self.assertIn("not selected in the company switcher", errors[0][1])
        self.assertEqual(self.create_contexts, [])
        self.assertFalse(self.Document.search([("document_key", "=", KEY_1)]))

    def test_a_company_the_user_cannot_access_is_refused(self):
        user = self._fiscal_user("fiscal_user_company")
        parsed = self._parsed(KEY_1, company=self.other_company)
        model = self.Document.with_user(user).with_context(
            allowed_company_ids=self.company.ids
        )
        documents, errors, _warnings = self._import(
            [(parsed.file_name, b"x")], [parsed], model=model
        )
        self.assertFalse(documents)
        self.assertIn("no access to the company", errors[0][1])
        self.assertEqual(self.create_contexts, [])

    def test_the_company_is_searched_in_the_order_of_the_roles(self):
        parsed = self._parsed(
            KEY_1,
            company_vats=(
                ("taker", "00000000000000"),
                ("issuer", self.company.partner_id.cnpj_cpf_stripped),
            ),
        )
        company, role = self.Document._edi_import_company(parsed)
        self.assertEqual((company, role), (self.company, "issuer"))
        with self.assertRaises(UserError):
            self.Document._edi_import_company(
                self._parsed(KEY_1, company_vats=(("recipient", "00000000000000"),))
            )

    def test_the_role_of_the_company_tells_the_direction_of_the_document(self):
        incoming = self._create_imported_document()
        incoming._edi_import_after_create(self._parsed(KEY_1), "recipient")
        self.assertEqual(incoming.issuer, "partner")
        self.assertEqual(incoming.fiscal_operation_type, "in")
        own = self._create_imported_document()
        own._edi_import_after_create(self._parsed(KEY_2), "issuer")
        self.assertEqual(own.issuer, "company")
        self.assertEqual(own.fiscal_operation_type, "out")
        self.assertTrue(own.imported_document)

    def test_the_file_is_kept_and_the_partners_it_created_are_recorded(self):
        document = self._create_imported_document()
        last = self.env["res.partner"].search([], order="id desc", limit=1)
        created = self.env["res.partner"].create({"name": "Born from the file"})
        document.with_context(
            edi_import_last_partner_id=last.id
        )._edi_import_after_create(self._parsed(KEY_1), "recipient")
        self.assertEqual(
            document.original_xml_file_id.raw, f"<xml>{KEY_1}</xml>".encode()
        )
        self.assertIn(created.display_name, document.message_ids[0].body)

    def test_a_reader_that_is_not_installed_refuses_the_file(self):
        parsed = self._parsed(KEY_1, reader="cte")
        with patch.object(
            type(self.Document), "_edi_import_read", lambda *args: parsed
        ):
            documents, errors, _warnings = self.Document._edi_import_files(
                [(parsed.file_name, b"x")]
            )
        self.assertFalse(documents)
        self.assertIn("no importer", errors[0][1])

    def test_the_suggestion_does_not_touch_the_values_of_the_file(self):
        document = self._create_imported_document(
            fiscal_operation_id=False,
            lines=[
                {
                    "quantity": 3.0,
                    "price_unit": 7.5,
                    "partner_cfop_id": self.env.ref("l10n_br_fiscal.cfop_5102").id,
                }
            ],
        )
        document._edi_import_after_create(self._parsed(KEY_1), "recipient")
        document._edi_import_suggest()
        line = document.fiscal_line_ids
        self.assertTrue(document.fiscal_operation_id)
        self.assertEqual(document.fiscal_operation_type, "in")
        self.assertEqual(line.fiscal_operation_id, document.fiscal_operation_id)
        self.assertEqual((line.quantity, line.price_unit), (3.0, 7.5))
        self.assertEqual(line.partner_cfop_id.code, "5102")

    def test_a_document_with_no_matching_operation_keeps_its_direction(self):
        """Nothing matches the CFOP: the operation stays empty, and the direction
        that the import gave the document is not recomputed away."""
        cfop = self.env.ref("l10n_br_fiscal.cfop_6102")
        for role, direction in (("recipient", "in"), ("issuer", "out")):
            document = self._create_imported_document(
                fiscal_operation_id=False,
                lines=[{"partner_cfop_id": cfop.id}],
            )
            document._edi_import_after_create(self._parsed(KEY_1), role)
            with patch.object(
                type(self.env["l10n_br_fiscal.operation.line"]),
                "_find_by_issuer_cfop",
                lambda *args: self.env["l10n_br_fiscal.operation.line"],
            ):
                document._edi_import_suggest()
            self.assertFalse(document.fiscal_operation_id)
            self.assertEqual(document.fiscal_operation_type, direction)

    def test_a_document_the_company_issued_gets_its_operation_as_an_output(self):
        """A document the company issued in another system is reviewed like any
        other: its operation is the one of its own CFOP, in the direction of out."""
        operation = self.env["l10n_br_fiscal.operation"].create(
            {
                "code": "TST-OUT",
                "name": "Own sale (test)",
                "fiscal_operation_type": "out",
                "fiscal_type": "sale",
            }
        )
        self.env["l10n_br_fiscal.operation.line"].create(
            {
                "fiscal_operation_id": operation.id,
                "name": "Own sale (test)",
                "cfop_internal_id": self.env.ref("l10n_br_fiscal.cfop_5102").id,
            }
        )
        operation.action_approve()
        document = self._create_imported_document(
            fiscal_operation_id=False,
            lines=[{"partner_cfop_id": self.env.ref("l10n_br_fiscal.cfop_5102").id}],
        )
        document._edi_import_after_create(self._parsed(KEY_1), "issuer")
        document.operation_name = operation.name
        document._edi_import_suggest()
        self.assertEqual(document.fiscal_operation_id, operation)
        self.assertEqual(document.fiscal_operation_type, "out")
        self.assertEqual(document.fiscal_line_ids.fiscal_operation_id, operation)
        self.assertEqual(document.fiscal_line_ids.import_state, "pending")

    def test_the_suggestion_can_run_again_without_undoing_a_decision(self):
        product = self.env["product.product"].create({"name": "Chosen by a person"})
        document = self._create_imported_document()
        line = document.fiscal_line_ids
        line.product_id = product
        line._apply_import_depara(uom=self.uom_unit)
        self.assertEqual(line.import_state, "resolved")
        document._edi_import_suggest()
        document._edi_import_suggest()
        self.assertEqual(line.import_state, "resolved")
        self.assertEqual(line.product_id, product)

    def test_a_product_mapped_for_the_same_supplier_enters_resolved(self):
        product = self.env["product.product"].create({"name": "Mapped product"})
        self.env["product.supplierinfo"].create(
            {
                "partner_id": self.supplier.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_id": product.id,
                "product_code": "SUP-1",
                "price": 1.0,
            }
        )
        with patch.object(
            type(self.env["l10n_br_fiscal.document.line"]),
            "_get_partner_product_code",
            lambda line: "SUP-1",
        ):
            document = self._create_imported_document()
            document._edi_import_suggest()
        line = document.fiscal_line_ids
        self.assertEqual(line.product_id, product)
        self.assertEqual(line.import_state, "resolved")

    def test_unknown_unit_with_a_product_mapped_by_the_supplier_awaits_review(self):
        """The supplier mapped the product, but the unit it declares now matches
        nothing: the product is set and the line still waits for a person."""
        product = self.env["product.product"].create({"name": "Mapped product"})
        self.env["product.supplierinfo"].create(
            {
                "partner_id": self.supplier.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_id": product.id,
                "product_code": "SUP-1",
                "price": 1.0,
            }
        )
        with patch.object(
            type(self.env["l10n_br_fiscal.document.line"]),
            "_get_partner_product_code",
            lambda line: "SUP-1",
        ):
            document = self._create_imported_document(
                lines=[{"partner_uom_code": "ZZZ"}]
            )
            document._edi_import_suggest()
        line = document.fiscal_line_ids
        self.assertEqual(line.product_id, product)
        self.assertEqual(line.import_state, "pending")

    def test_the_review_of_a_document_the_company_issued_learns_no_supplier(self):
        product = self.env["product.product"].create({"name": "Sold product"})
        customer = self.env["res.partner"].create({"name": "Customer of the sale"})
        for direction, learned in (("out", 0), ("in", 1)):
            document = self._create_imported_document(
                partner=customer,
                fiscal_operation_type=direction,
                lines=[{"product_id": product.id}],
            )
            document.fiscal_operation_type = direction
            document.fiscal_line_ids.action_resolve_line()
            self.assertEqual(
                self.env["product.supplierinfo"].search_count(
                    [("partner_id", "=", customer.id)]
                ),
                learned,
            )

    def test_a_product_mapped_for_another_supplier_is_not_resolved(self):
        product = self.env["product.product"].create({"name": "Mapped elsewhere"})
        other = self.env["res.partner"].create({"name": "Another supplier"})
        self.env["product.supplierinfo"].create(
            {
                "partner_id": other.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_code": "SUP-1",
                "price": 1.0,
            }
        )
        with patch.object(
            type(self.env["l10n_br_fiscal.document.line"]),
            "_get_partner_product_code",
            lambda line: "SUP-1",
        ):
            document = self._create_imported_document()
            document._edi_import_suggest()
        self.assertFalse(document.fiscal_line_ids.product_id)
        self.assertEqual(document.fiscal_line_ids.import_state, "pending")

    def test_unknown_unit_stays_pending_by_every_path(self):
        """A unit the supplier declared that matched nothing: the line is pending,
        the confirmation of the suggestions leaves it out, and the document cannot
        be confirmed."""
        product = self.env["product.product"].create({"name": "Matched product"})
        document = self._create_imported_document(
            lines=[
                {"product_id": product.id, "partner_uom_code": "ZZZ"},
                {"product_id": product.id, "partner_uom_code": "UN"},
            ]
        )
        document._edi_import_suggest()
        unknown, known = document.fiscal_line_ids
        self.assertEqual(unknown.import_state, "pending")
        self.assertEqual(known.import_state, "matched")
        # a suggestion whose unit is not confirmed is left out and counted
        unknown.import_state = "matched"
        action = document.action_import_confirm_suggestions()
        self.assertEqual(known.import_state, "resolved")
        self.assertEqual(unknown.import_state, "matched")
        self.assertEqual(action["tag"], "display_notification")
        self.assertIn("1 line(s)", action["params"]["message"])
        self.assertIn("ZZZ", document.import_warning)
        with self.assertRaises(UserError) as error:
            document.action_document_confirm()
        self.assertIn(unknown.name, str(error.exception))

    def test_confirming_the_suggestions_resolves_the_matched_lines_at_once(self):
        product = self.env["product.product"].create({"name": "Matched product"})
        document = self._create_imported_document(
            lines=[{"product_id": product.id}, {"product_id": product.id}]
        )
        self.assertEqual(
            document.fiscal_line_ids.mapped("import_state"), ["matched"] * 2
        )
        self.assertTrue(document.action_import_confirm_suggestions())
        self.assertEqual(document.import_state, "resolved")

    def test_a_document_with_lines_not_reviewed_cannot_be_confirmed(self):
        document = self._create_imported_document()
        with self.assertRaises(UserError) as error:
            document.action_document_confirm()
        self.assertIn("Imported item", str(error.exception))
        self.assertEqual(document.state_edoc, "em_digitacao")

    def test_a_document_with_every_line_reviewed_goes_on_to_the_confirmation(self):
        product = self.env["product.product"].create({"name": "Matched product"})
        document = self._create_imported_document(lines=[{"product_id": product.id}])
        document.action_import_confirm_suggestions()
        with patch.object(
            type(self.Document), "_trigger_fsm", return_value=True
        ) as trigger:
            document.action_document_confirm()
        trigger.assert_called_once()

    def test_a_document_the_company_issued_is_confirmed_as_authorized(self):
        """Issued in another system, it is authorized already: confirming it must
        not validate and send it again."""
        product = self.env["product.product"].create({"name": "Matched product"})
        document = self._create_imported_document(
            issuer="company", lines=[{"product_id": product.id}]
        )
        document.action_import_confirm_suggestions()
        with patch.object(
            type(self.Document), "_trigger_fsm", return_value=True
        ) as trigger, patch.object(type(self.Document), "action_document_send") as send:
            document.action_document_confirm()
        trigger.assert_called_once_with("action_confirm_authorized")
        send.assert_not_called()

    def test_a_document_the_company_issued_is_also_refused_with_lines_to_review(self):
        document = self._create_imported_document(issuer="company")
        with self.assertRaises(UserError):
            document.action_document_confirm()

    def test_the_warning_is_unset_when_there_is_nothing_to_say(self):
        document = self._create_imported_document()
        self.assertFalse(document.import_warning)
        document.fiscal_operation_id = False
        self.assertIn("No fiscal operation", document.import_warning)

    def test_the_review_is_also_a_state_of_the_list(self):
        document = self._create_imported_document()
        self.assertEqual(document.import_state, "pending")
        self.assertEqual(
            self.Document.search(
                [("imported_document", "=", True), ("import_state", "=", "pending")]
            ),
            document,
        )

    def test_a_note_already_imported_is_found_by_key_and_company(self):
        document = self._create_imported_document(document_key=KEY_3)
        found = self.Document._edi_import_find_existing(
            self._parsed(KEY_3), self.company
        )
        self.assertEqual(found, document)
        self.assertFalse(
            self.Document._edi_import_find_existing(
                self._parsed(KEY_3), self.other_company
            )
        )

    def test_a_user_who_cannot_create_contacts_gets_a_clear_message_per_file(self):
        """The file needs a partner to be registered and the user may not create
        contacts: that file is refused saying so, nothing is created for it, and
        the others of the batch enter."""
        user = self._fiscal_user("fiscal_user_no_partner")
        self.assertFalse(
            self.env["res.partner"]
            .with_user(user)
            .check_access_rights("create", raise_exception=False)
        )
        needs, plain = self._parsed(KEY_1), self._parsed(KEY_2)
        test = self
        document_model = type(self.Document)
        by_name = {needs.file_name: needs, plain.file_name: plain}

        def read(model, name, content):
            return by_name.get(name)

        def create(model, parsed_file, company, role):
            if parsed_file is needs:
                model.env["res.partner"].create({"name": "Needed issuer"})
            return test._create_imported_document(
                company=company, model=model, document_key=parsed_file.access_key
            )

        model = self.Document.with_user(user).with_context(
            allowed_company_ids=self.company.ids
        )
        with patch.object(document_model, "_edi_import_read", read), patch.object(
            document_model, "_edi_import_create", create
        ):
            documents, errors, _warnings = model._edi_import_files(
                [(needs.file_name, b"x"), (plain.file_name, b"x")]
            )
        self.assertEqual(documents.mapped("document_key"), [KEY_2])
        self.assertEqual([name for name, _msg in errors], [needs.file_name])
        message = errors[0][1]
        self.assertIn("59.594.315/0001-57", message)
        self.assertIn("not allowed to create contacts", message)
        self.assertIn("import the file again", message)
        self.assertFalse(
            self.env["res.partner"].search([("name", "=", "Needed issuer")])
        )

    def test_a_common_fiscal_user_imports_and_learns_as_the_author(self):
        """The fiscal user is not a manager and has no right on purchases: the
        document, the file and the de-para are still born in their name."""
        user = self._fiscal_user("fiscal_user_import")
        product = self.env["product.product"].create({"name": "Learned product"})
        parsed = self._parsed(KEY_1)
        documents, errors, _warnings = self._import(
            [(parsed.file_name, b"x")],
            [parsed],
            model=self.Document.with_user(user).with_context(
                allowed_company_ids=self.company.ids
            ),
            lines=[{"product_id": product.id, "partner_uom_code": "UN"}],
        )
        self.assertEqual((len(documents), errors), (1, []))
        self.assertEqual(documents.create_uid, user)
        self.assertEqual(documents.original_xml_file_id.create_uid, user)
        line = documents.fiscal_line_ids.with_user(user)
        line.action_resolve_line()
        self.assertEqual(line.import_state, "resolved")
        self.assertEqual(line.import_supplierinfo_id.sudo().create_uid, user)
