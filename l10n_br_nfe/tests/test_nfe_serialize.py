# @ 2020 KMEE INFORMATICA LTDA - www.kmee.com.br -
#   Gabriel Cardoso de Faria <gabriel.cardoso@kmee.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from datetime import datetime
from xmldiff import main

from odoo.tools import config
import os
import logging

from odoo.tests.common import TransactionCase
from odoo.addons import l10n_br_nfe
from odoo.addons.l10n_br_fiscal.constants.fiscal import PROCESSADOR_OCA
from odoo.addons.spec_driven_model import hooks

_logger = logging.getLogger(__name__)


class TestNFeExport(TransactionCase):
    def setUp(self):
        super(TestNFeExport, self).setUp()
        hooks.register_hook(self.env, 'l10n_br_nfe',
                            'odoo.addons.l10n_br_nfe_spec.models.v4_00.leiauteNFe')
        self.nfe = self.env.ref('l10n_br_nfe.demo_nfe_same_state')
        self.nfe.write(
            {'document_type_id': self.env.ref('l10n_br_fiscal.document_55').id,
             'company_id': self.env.ref('l10n_br_base.empresa_lucro_presumido').id,
             'company_number': 3,
             'processador_edoc': PROCESSADOR_OCA,
             })
        self.nfe.company_id.processador_edoc = PROCESSADOR_OCA
        if self.nfe.state != 'em_digitacao':  # 2nd test run
            self.nfe.action_document_back2draft()

        for line in self.nfe.line_ids:
            line._onchange_product_id_fiscal()
            line._onchange_fiscal_operation_id()
            line._onchange_fiscal_operation_line_id()

        self.nfe.company_id.street_number = '3'

    def test_serialize_xml(self):

        for nfe in self.nfe_list:
            nfe_id = nfe['record_id']

            self.prepare_test_nfe(nfe_id)

            xml_path = os.path.join(
                l10n_br_nfe.__path__[0], 'tests', 'nfe', 'v4_00', 'leiauteNFe',
                nfe['xml_file'])
            nfe_id.action_document_confirm()
            nfe_id.date = datetime.strptime(
                '2020-01-01T11:00:00', '%Y-%m-%dT%H:%M:%S')
            nfe_id.date_in_out = datetime.strptime(
                '2020-01-01T11:00:00', '%Y-%m-%dT%H:%M:%S')
            nfe_id.nfe40_cNF = '06277716'
            nfe_id.nfe40_Id = 'NFeTest'
            nfe_id.nfe40_nNF = '1'
            nfe_id.nfe40_cDV = '1'
            nfe_id.with_context(lang='pt_BR')._document_export()
            output = os.path.join(config['data_dir'], 'filestore',
                                  self.cr.dbname,  nfe_id.file_xml_id.store_fname)
            _logger.info("XML file saved at %s" % (output,))
            nfe_id.company_id.country_id.name = 'Brazil'  # clean mess
            diff = main.diff_files(xml_path, output)
            _logger.info("Diff with expected XML (if any): %s" % (diff,))
            assert len(diff) == 0
