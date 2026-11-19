# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from odoo import fields

from odoo.addons.l10n_br_fiscal_edi.tests.common import KEY_1, EdiImportCase
from odoo.addons.queue_job.tests.common import trap_jobs


def _processor():
    event = SimpleNamespace(
        cStat="135",
        xMotivo="ok",
        nProt="1",
        dhRegEvento="2026-11-18T10:00:00-03:00",
    )
    answer = SimpleNamespace(
        retorno=SimpleNamespace(status_code=200, _content=b"<ok/>"),
        resposta=SimpleNamespace(retEvento=[SimpleNamespace(infEvento=event)]),
    )
    return SimpleNamespace(
        ciencia_da_operacao=lambda key, cnpj: answer,
        confirmacao_da_operacao=lambda key, cnpj: answer,
    )


class TestNfeManifestOnConfirm(EdiImportCase):
    """The manifestation that the company chose, registered when an NF-e received
    from a supplier is confirmed."""

    def _document(self, days=2, **values):
        document = self._create_imported_document(
            review=False,
            document_key=KEY_1,
            document_date=fields.Datetime.now() - timedelta(days=days),
            **values,
        )
        document.authorization_date = document.document_date
        return document

    def _confirm(self, document, option):
        document.company_id.sudo().nfe_manifest_on_document_confirm = option
        with trap_jobs() as trap:
            document.action_document_confirm()
        return trap

    def _perform(self, trap):
        with mock.patch.object(
            type(self.env["l10n_br_nfe.md_event"]),
            "_get_processor",
            return_value=_processor(),
        ):
            trap.perform_enqueued_jobs()

    def _events(self):
        return self.env["l10n_br_nfe.md_event"].search([("access_key", "=", KEY_1)])

    def test_nothing_is_registered_by_default(self):
        trap = self._confirm(self._document(), "none")

        trap.assert_jobs_count(0)
        self.assertEqual(self.company.nfe_manifest_on_document_confirm, "none")

    def test_the_acknowledgement_is_registered_by_a_job_when_confirming(self):
        document = self._document(days=2)

        trap = self._confirm(document, "ciencia")

        trap.assert_jobs_count(1)
        self.assertFalse(self._events())
        self._perform(trap)
        self.assertEqual(self._events().event_type, "ciente")
        self.assertEqual(self._events().state, "done")

    def test_the_acknowledgement_is_skipped_with_a_notice_after_ten_days(self):
        document = self._document(days=11)

        trap = self._confirm(document, "ciencia")

        trap.assert_jobs_count(0)
        self.assertEqual(document.state_edoc, "autorizada")
        self.assertIn("10 days", "".join(document.message_ids.mapped("body")))

    def test_the_confirmation_is_registered_even_after_ten_days(self):
        document = self._document(days=40)

        trap = self._confirm(document, "confirmacao")

        trap.assert_jobs_count(1)
        self._perform(trap)
        self.assertEqual(self._events().event_type, "confirmado")

    def test_a_manifestation_already_registered_is_not_repeated(self):
        document = self._document()
        self.env["l10n_br_nfe.md_event"].create(
            {
                "access_key": KEY_1,
                "event_type": "ciente",
                "state": "done",
                "company_id": self.company.id,
            }
        )

        trap = self._confirm(document, "ciencia")

        trap.assert_jobs_count(0)

    def test_a_document_that_was_not_imported_is_not_manifested(self):
        document = self._document()
        document.imported_document = False

        trap = self._confirm(document, "confirmacao")

        trap.assert_jobs_count(0)

    def test_the_event_of_a_common_fiscal_user_is_registered_by_the_job(self):
        user = self._fiscal_user("manifest_fiscal")
        user.email = "manifest_fiscal@example.com"
        document = (
            self._document()
            .with_user(user)
            .with_context(allowed_company_ids=self.company.ids)
        )

        trap = self._confirm(document, "confirmacao")
        self._perform(trap)

        self.assertEqual(self._events().state, "done")
