# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
from datetime import datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from lxml import etree

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from .common import MODEL, ConnectionCommon
from .fake_bank import FAKE_MTLS, reset_state


def _pkcs12(common_name, password=None):
    """A PKCS12 bundle (key and self-signed certificate) and its PEM certificate."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    encryption = (
        serialization.BestAvailableEncryption(password.encode())
        if password
        else serialization.NoEncryption()
    )
    bundle = pkcs12.serialize_key_and_certificates(b"a1", key, cert, None, encryption)
    return bundle, cert.public_bytes(serialization.Encoding.PEM)


@tagged("post_install", "-at_install")
class TestConnectionCertificate(ConnectionCommon, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_connection()

    def setUp(self):
        super().setUp()
        reset_state()

    def _certificate(self, common_name="EMPRESA:91300766000147", password="segredo"):
        bundle, pem = _pkcs12(common_name, password)
        record = self.env["certificate.certificate"].create(
            {
                "name": common_name,
                "content": base64.b64encode(bundle),
                "pkcs12_password": password,
                "company_id": self.env.company.id,
            }
        )
        return record, pem

    def _mtls_connection(self, **values):
        return self._create_connection(adapter=FAKE_MTLS, client_secret=False, **values)

    def test_certificate_record_reaches_the_bank(self):
        record, pem = self._certificate()
        connection = self._mtls_connection(
            certificate=base64.b64encode(b"old pem"), certificate_id=record.id
        )
        self.assertTrue(connection.uses_certificate)
        # The prepared config carries the PEM of the record, not the binary field.
        _adapter_class, config = connection._l10n_br_bank_prepare_adapter()
        self.assertEqual(config.certificado_pem, pem)
        self.assertIn(b"PRIVATE KEY", config.chave_pem)

    def test_download_the_public_part_of_a_customer_a1(self):
        record, _pem = self._certificate("A1 DO CLIENTE")
        connection = self._mtls_connection(certificate_id=record.id)
        action = connection.action_download_certificate_pem()
        self.assertIn(
            f"certificate.certificate/{record.id}/pem_certificate", action["url"]
        )

    def test_pem_fields_without_a_certificate_record(self):
        _bundle, pem = _pkcs12("SEM REGISTRO")
        connection = self._mtls_connection(
            certificate=base64.b64encode(pem),
            private_key=base64.b64encode(b"-----BEGIN PRIVATE KEY-----"),
        )
        _adapter_class, config = connection._l10n_br_bank_prepare_adapter()
        self.assertEqual(config.certificado_pem, pem)

    def test_certificate_without_private_key_is_refused(self):
        _bundle, pem = _pkcs12("SO PUBLICO")
        record = self.env["certificate.certificate"].create(
            {"name": "so publico", "content": base64.b64encode(pem)}
        )
        # Refused on save, by the configuration check of the connection.
        with self.assertRaisesRegex(UserError, "no private key"):
            self._mtls_connection(certificate_id=record.id)

    def test_new_certificate_asks_to_renew_the_bank_credential(self):
        first, _pem = self._certificate("PRIMEIRO")
        connection = self._mtls_connection(certificate_id=first.id)
        self.assertTrue(connection.certificate_registered_fingerprint)
        self.assertFalse(connection.certificate_renewal_needed)
        renewed, _pem = self._certificate("RENOVADO")
        connection.certificate_id = renewed
        self.assertTrue(connection.certificate_renewal_needed)
        connection.action_certificate_renewed_at_bank()
        self.assertFalse(connection.certificate_renewal_needed)
        self.assertEqual(
            connection.certificate_registered_fingerprint,
            connection.certificate_fingerprint,
        )
        # A new environment comes with a new credential: no warning.
        other, _pem = self._certificate("OUTRO")
        connection.write({"certificate_id": other.id, "environment": "prod"})
        self.assertFalse(connection.certificate_renewal_needed)

    def test_test_certificate_only_in_the_test_environment(self):
        connection = self._mtls_connection(name="Bradesco Teste")
        with self.assertRaisesRegex(UserError, "no certificate"):
            connection.action_download_certificate_pem()
        result = connection.action_generate_test_certificate()
        self.assertEqual(result["tag"], "display_notification")
        record = connection.certificate_id
        self.assertTrue(record.private_key_id)
        self.assertTrue(record.pem_certificate)
        cert = x509.load_pem_x509_certificate(base64.b64decode(record.pem_certificate))
        names = {attr.oid: attr.value for attr in cert.subject}
        self.assertTrue(names[NameOID.COMMON_NAME].endswith(":91300766000147"))
        self.assertEqual(names[NameOID.COUNTRY_NAME], "BR")
        self.assertIn(names[NameOID.ORGANIZATION_NAME], names[NameOID.COMMON_NAME])
        self.assertEqual(cert.signature_hash_algorithm.name, "sha256")
        self.assertEqual(cert.public_key().key_size, 2048)
        # Downloading is its own action: only the public part, never the key.
        action = connection.action_download_certificate_pem()
        self.assertIn(
            f"certificate.certificate/{record.id}/pem_certificate", action["url"]
        )
        self.assertIn("download=true", action["url"])
        # The form reads binaries with bin_size: the size, not the content.
        connection.invalidate_recordset()
        on_form = connection.with_context(bin_size=True)
        self.assertEqual(
            on_form.certificate_fingerprint, connection.certificate_fingerprint
        )
        self.assertFalse(on_form.certificate_renewal_needed)
        # It goes to the bank as any certificate record.
        _adapter_class, config = connection._l10n_br_bank_prepare_adapter()
        self.assertEqual(
            config.certificado_pem, base64.b64decode(record.pem_certificate)
        )
        connection.environment = "prod"
        with self.assertRaises(UserError):
            connection.action_generate_test_certificate()


@tagged("post_install", "-at_install")
class TestConnectionCertificateAccess(ConnectionCommon, TransactionCase):
    """The finance user who keeps the bank connections picks the A1 of the company
    and pastes the PEM pair, without being a fiscal manager or a system admin."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_connection()
        cls.finance = new_test_user(
            cls.env,
            login="conn-finance",
            groups="base.group_user,account.group_account_manager,"
            "l10n_br_bank_connection.group_bank_connection_admin",
        )
        bundle, cls.pem = _pkcs12("EMPRESA:91300766000147", "segredo")
        cls.a1 = cls.env["certificate.certificate"].create(
            {
                "name": "A1 da empresa",
                "content": base64.b64encode(bundle),
                "pkcs12_password": "segredo",
                "company_id": cls.env.company.id,
            }
        )
        cls.connection = cls._create_connection(
            adapter=FAKE_MTLS, client_secret=False, certificate_id=False
        )

    def test_finance_user_picks_the_certificate_of_the_company(self):
        connection = self.connection.with_user(self.finance)
        # What the many2one does: search the options and show the name.
        found = self.env["certificate.certificate"].with_user(self.finance)
        self.assertIn(self.a1.id, [rid for rid, _name in found.name_search("")])
        connection.write({"certificate_id": self.a1.id})
        self.assertTrue(connection.certificate_id.display_name)
        self.assertEqual(
            connection.read(["certificate_id"])[0]["certificate_id"][0], self.a1.id
        )
        self.assertTrue(connection.certificate_fingerprint)

    def test_finance_user_never_reads_the_a1_secrets(self):
        certificate = self.a1.with_user(self.finance)
        self.assertEqual(certificate.read(["display_name"])[0]["id"], self.a1.id)
        for field_name in ("content", "pkcs12_password", "private_key_id"):
            self.assertNotIn(field_name, certificate.fields_get())
            with self.assertRaises(AccessError):
                certificate.read([field_name])
        # Nothing of the record leaks when no field is asked either.
        self.assertFalse({"content", "pkcs12_password"} & set(certificate.read()[0]))

    def test_finance_user_cannot_change_certificates(self):
        certificate = self.a1.with_user(self.finance)
        with self.assertRaises(AccessError):
            certificate.write({"name": "other"})
        with self.assertRaises(AccessError):
            certificate.unlink()
        with self.assertRaises(AccessError):
            self.env["certificate.certificate"].with_user(self.finance).create(
                {"name": "new", "content": base64.b64encode(b"x")}
            )

    def test_finance_user_of_another_company_does_not_see_the_a1(self):
        other = self.env["res.company"].create({"name": "Other company"})
        user = new_test_user(
            self.env,
            login="conn-finance-2",
            groups="base.group_user,account.group_account_manager,"
            "l10n_br_bank_connection.group_bank_connection_admin",
            company_id=other.id,
            company_ids=[(6, 0, other.ids)],
        )
        found = self.env["certificate.certificate"].with_user(user)
        self.assertFalse(found.search([("id", "=", self.a1.id)]))

    def test_finance_user_pastes_the_pem_pair(self):
        connection = self.connection.with_user(self.finance)
        key = b"-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n"
        connection.write(
            {
                "certificate": base64.b64encode(self.pem),
                "private_key": base64.b64encode(key),
            }
        )
        self.assertTrue(connection.certificate_fingerprint)

    def _form_spec(self, connection):
        """The specification the web client sends: every field of the form view."""
        view = connection.get_view(view_type="form")
        spec = {}
        for node in etree.fromstring(view["arch"]).iter("field"):
            name = node.get("name")
            field = connection._fields.get(name)
            if field is None or field.type in ("one2many", "many2many"):
                continue
            spec[name] = (
                {"fields": {"display_name": {}}} if field.type == "many2one" else {}
            )
        return spec

    def test_finance_user_loads_and_edits_the_form(self):
        connection = self.connection.with_user(self.finance).with_context(bin_size=True)
        spec = self._form_spec(connection)
        self.assertIn("certificate_id", spec)
        self.assertIn("certificate", spec)
        # Opening the connection, then the PEM upload and the pick of the A1: the
        # calls of the web client, with the context of the form.
        connection.web_read(spec)
        pem = base64.b64encode(self.pem).decode()
        result = connection.onchange({"certificate": pem}, ["certificate"], spec)
        self.assertIn("value", result)
        result = connection.onchange(
            {"certificate_id": self.a1.id}, ["certificate_id"], spec
        )
        self.assertIn("value", result)
        connection.web_save({"certificate_id": self.a1.id}, spec)
        self.assertEqual(connection.certificate_id, self.a1)
        # A new connection of a bank that takes the A1 (Bradesco): the adapter
        # onchange proposes the A1 of the company.
        result = (
            self.env[MODEL]
            .with_user(self.finance)
            .onchange(
                {"adapter": "bradesco", "company_id": self.env.company.id},
                ["adapter"],
                spec,
            )
        )
        proposed = self.env["certificate.certificate"].browse(
            result["value"]["certificate_id"]["id"]
        )
        self.assertTrue(proposed.is_valid)
        self.assertIn(proposed.company_id.id, [False, self.env.company.id])


@tagged("post_install", "-at_install")
class TestConnectionCertificateDefault(ConnectionCommon, TransactionCase):
    """Only the banks that take the A1 of the company get it proposed: the Pix of
    the Sicredi uses a certificate issued by the bank, and the A1 (which takes
    precedence over the PEM fields) made the bank refuse the token."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_connection()
        bundle, _pem = _pkcs12("EMPRESA:91300766000147", "segredo")
        cls.a1 = cls.env["certificate.certificate"].create(
            {
                "name": "A1 da empresa",
                "content": base64.b64encode(bundle),
                "pkcs12_password": "segredo",
                "company_id": cls.env.company.id,
            }
        )

    def _assert_company_certificate(self, proposed):
        """A valid certificate of the company (the database may hold others)."""
        self.assertTrue(proposed)
        self.assertTrue(proposed.is_valid)
        self.assertIn(proposed.company_id.id, [False, self.env.company.id])

    def _proposed(self, **values):
        connection = self.Connection.new(
            dict(values, company_id=self.env.company.id, certificate_id=False)
        )
        self.assertTrue(connection.uses_certificate)
        connection._onchange_certificate_default()
        return connection.certificate_id

    def test_pix_sicredi_gets_no_company_certificate(self):
        proposed = self._proposed(adapter="pix_bacen", pix_profile="sicredi")
        self.assertFalse(proposed)

    def test_pix_of_banks_with_their_own_certificate(self):
        for profile in ("inter", "itau", "santander", "sicoob", "efi"):
            with self.subTest(profile=profile):
                proposed = self._proposed(adapter="pix_bacen", pix_profile=profile)
                self.assertFalse(proposed)

    def test_pix_bb_and_bradesco_get_the_company_certificate(self):
        for profile in ("bb", "bradesco"):
            with self.subTest(profile=profile):
                proposed = self._proposed(adapter="pix_bacen", pix_profile=profile)
                self._assert_company_certificate(proposed)

    def test_bradesco_and_bb_adapters_get_the_company_certificate(self):
        for adapter in ("bradesco", "bb"):
            with self.subTest(adapter=adapter):
                connection = self.Connection.new(
                    {
                        "adapter": adapter,
                        "company_id": self.env.company.id,
                        "certificate_id": False,
                    }
                )
                if not connection.uses_certificate:
                    self.skipTest(f"{adapter} takes no certificate in this brbank")
                connection._onchange_certificate_default()
                self._assert_company_certificate(connection.certificate_id)

    def test_changing_the_profile_to_sicredi_does_not_keep_the_proposal(self):
        connection = self.Connection.new(
            {
                "adapter": "pix_bacen",
                "pix_profile": "bb",
                "company_id": self.env.company.id,
                "certificate_id": False,
            }
        )
        connection._onchange_certificate_default()
        self._assert_company_certificate(connection.certificate_id)
        # What the user does next: picks Sicredi and clears the proposed A1.
        connection.pix_profile = "sicredi"
        connection.certificate_id = False
        connection._onchange_certificate_default()
        self.assertFalse(connection.certificate_id)

    def test_pem_fields_stay_visible_with_a_certificate_record(self):
        view = self.Connection.get_view(
            self.env.ref("l10n_br_bank_connection.bank_connection_form").id
        )
        arch = etree.fromstring(view["arch"])
        for name in ("certificate", "private_key"):
            field = arch.xpath(f"//field[@name='{name}']")[0]
            self.assertNotIn("certificate_id", field.get("invisible") or "", name)
