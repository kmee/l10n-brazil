# Copyright 2023 - TODAY, Akretion - Raphael Valyi <raphael.valyi@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).

from datetime import date
from os import path

from odoo.tests import common
from odoo.tools.misc import format_date

from odoo.addons import l10n_br_sped_efd_icms_ipi
from odoo.addons.l10n_br_sped_base.models.sped_mixin import SPED_ENCODING
from odoo.addons.l10n_br_sped_efd_icms_ipi.models.sped_efd_icms_ipi import (
    fiscal_obs_code,
)


class SpedTest(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.demo_path = path.join(l10n_br_sped_efd_icms_ipi.__path__[0], "demo")

    def test_import_efd_icms_ipi(self):
        self.env["l10n_br_sped.mixin"]._flush_registers("efd_icms_ipi")
        file_path = path.join(self.demo_path, "demo_efd_icms_ipi.txt")
        sped_mixin = self.env["l10n_br_sped.mixin"]
        declaration = sped_mixin._import_file(file_path, "efd_icms_ipi")
        sped = declaration._generate_sped_text()
        with open(file_path, encoding=SPED_ENCODING) as f:
            target_content = f.read()
            # print(sped)
            self.assertEqual(sped.strip(), target_content.strip())

    def _create_inventory(self, dt_inv):
        self.env["l10n_br_sped.mixin"]._flush_registers("efd_icms_ipi")
        file_path = path.join(self.demo_path, "demo_efd_icms_ipi.txt")
        declaration = self.env["l10n_br_sped.mixin"]._import_file(
            file_path, "efd_icms_ipi"
        )
        return self.env["l10n_br_sped.efd_icms_ipi.h005"].create(
            {"declaration_id": declaration.id, "DT_INV": dt_inv, "MOT_INV": "01"}
        )

    def test_h005_name_is_the_inventory_date(self):
        h005 = self._create_inventory(date(2023, 1, 31))
        name = h005.name_get()[0][1]
        self.assertNotIn("l10n_br_sped.efd_icms_ipi.h005", name)
        self.assertIn(format_date(self.env, date(2023, 1, 31)), name)

    def test_h005_name_search_by_the_inventory_date(self):
        h005 = self._create_inventory(date(2023, 1, 31))
        other = h005.copy({"DT_INV": date(2022, 12, 31)})
        H005 = self.env["l10n_br_sped.efd_icms_ipi.h005"]
        domain = [("id", "in", (h005 | other).ids)]

        found = H005.name_search(format_date(self.env, date(2023, 1, 31)), args=domain)
        self.assertEqual([r[0] for r in found], h005.ids)

        self.assertFalse(H005.name_search("31/12/1999", args=domain))

    def test_c195_c197_generation(self):
        """A document carrying a fiscal observation and an adjustment line
        must generate C195 (observation) + C197 (adjustment) registers,
        backed by a 0460 observation-code register."""
        demo = self.env.ref("l10n_br_fiscal.demo_nfe_same_state")
        demo.manual_fiscal_additional_data = "Observacao fiscal de teste C195"
        line = demo.fiscal_line_ids[0]
        line.partner_icms_tax_benefit_code = "SP12345678"
        line.icms_relief_value = 7.50

        declaration = self.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {"company_id": demo.company_id.id, "debug": True}
        )
        declaration.button_populate_sped_from_odoo()

        c195 = self.env["l10n_br_sped.efd_icms_ipi.c195"].search(
            [("declaration_id", "=", declaration.id)]
        )
        self.assertTrue(c195, "No C195 register generated for the observation")
        self.assertIn(
            fiscal_obs_code("Observacao fiscal de teste C195"),
            c195.mapped("COD_OBS"),
        )

        reg0460 = self.env["l10n_br_sped.efd_icms_ipi.0460"].search(
            [("declaration_id", "=", declaration.id)]
        )
        self.assertIn("Observacao fiscal de teste C195", reg0460.mapped("TXT"))

        c197 = self.env["l10n_br_sped.efd_icms_ipi.c197"].search(
            [("declaration_id", "=", declaration.id)]
        )
        self.assertTrue(c197, "No C197 register generated for the adjustment")
        self.assertIn("SP12345678", c197.mapped("COD_AJ"))

    def test_c197_uses_sped_cod_aj(self):
        """When the accountant sets a Tabela 5.3 code on the relief, C197 must
        use it as COD_AJ instead of the declared cBenef."""
        demo = self.env.ref("l10n_br_fiscal.demo_nfe_same_state")
        # C197 is a child of C195, so the document needs an observation for
        # the parent register to exist (see also the "generic C195" gap).
        demo.manual_fiscal_additional_data = "Observacao fiscal de teste C195"
        line = demo.fiscal_line_ids[0]
        relief = self.env["l10n_br_fiscal.icms.relief"].create(
            {
                "code": "RJ000001",
                "name": "Desoneracao de teste",
                "sped_cod_aj": "RJ999999",
            }
        )
        line.icms_relief_id = relief
        line.icms_relief_value = 12.34
        line.partner_icms_tax_benefit_code = "SP12345678"

        declaration = self.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {"company_id": demo.company_id.id, "debug": True}
        )
        declaration.button_populate_sped_from_odoo()

        c197 = self.env["l10n_br_sped.efd_icms_ipi.c197"].search(
            [("declaration_id", "=", declaration.id)]
        )
        self.assertTrue(c197, "No C197 register generated for the adjustment")
        self.assertIn("RJ999999", c197.mapped("COD_AJ"))
        self.assertNotIn("SP12345678", c197.mapped("COD_AJ"))
