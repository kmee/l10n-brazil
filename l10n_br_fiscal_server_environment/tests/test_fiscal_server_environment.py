# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.server_environment.tests.common import ServerEnvironmentCase

GLOBAL_CONFIG = """
[res_company]
nfe_environment = 2
nfse_environment = 2

[res_company.Metalúrgica Santa Rita Ltda]
nfe_environment = 1
"""


class TestFiscalServerEnvironment(ServerEnvironmentCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref(
            "l10n_br_fiscal_server_environment.company_metalurgica_santa_rita"
        )
        cls.other_company = cls.env["res.company"].create(
            {"name": "Papelaria Boa Vista Ltda"}
        )

    def test_environment_from_file(self):
        with self.load_config(public=GLOBAL_CONFIG):
            self.assertEqual(self.company.nfe_environment, "1")
            self.assertEqual(self.company.nfse_environment, "2")
            self.assertEqual(self.other_company.nfe_environment, "2")
            self.assertFalse(self.other_company.x_nfe_environment_env_is_editable)

    def test_environment_without_file_uses_registered_value(self):
        self.other_company.nfe_environment = "1"
        with self.load_config(public=""):
            self.assertEqual(self.other_company.nfe_environment, "1")
            self.assertTrue(self.other_company.x_nfe_environment_env_is_editable)
