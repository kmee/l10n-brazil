# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64

from odoo import api, models
from odoo.tests import Form
from odoo.tools import file_open


class DocumentImportWizard(models.TransientModel):
    _inherit = "l10n_br_fiscal.document.import.wizard"

    @api.model
    def _import_demo_files(self, module, relative_paths):
        """Import the sample NF-e that a module ships in its demo data, by the
        same wizard a person uses.

        :param module: name of the module that holds the files
        :param relative_paths: paths of the files inside the module
        :return: the bills generated from the files
        """
        company = self.env.ref("l10n_br_base.empresa_lucro_presumido")
        self = self.with_company(company)
        moves = self.env["account.move"]
        for path in relative_paths:
            with file_open(f"{module}/{path}", "rb") as sample:
                content = sample.read()
            wizard = self.create({"company_id": company.id})
            with Form(wizard) as wizard_form:
                wizard_form.file = base64.b64encode(content)
                wizard_form.fiscal_operation_id = self.env.ref(
                    "l10n_br_fiscal.fo_compras"
                )
            action = wizard.action_import_and_open_move()
            moves |= self.env["account.move"].browse(action["res_id"])
        return moves
