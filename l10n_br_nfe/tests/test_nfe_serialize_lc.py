# @ 2020 KMEE INFORMATICA LTDA - www.kmee.com.br -
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import os
from .test_nfe_serialize import TestNFeExport

class TestNFeExportLC(TestNFeExport):
    def setUp(self):
        super().setUp()

        company_id = self.env.ref('l10n_br_base.empresa_lucro_presumido')
        company_id.certificate_nfe_id = self.cert

        self.nfe_list = [
            {
                'record_id':
                    self.env.ref(
                        'l10n_br_nfe.demo_nfe_same_state'),
                'xml_file':
                    'NFe35200697231608000169550010000000111855451724-nf-e.xml',
            },
            {
                'record_id': self.env.ref(
                        'l10n_br_nfe.demo_nfe_natural_icms_18_red_51_11'
                ),
                'xml_file':
                    'NFe35210381583054000129550010000000021659443040-nf-e.xml',
            },
            {
                'record_id':
                    self.env.ref('l10n_br_nfe.demo_nfe_natural_icms_7_IPI_15_sp_am'),
                'xml_file':
                    'NFe35210381583054000129550010000000031659634756-nf-e.xml',
            },
            {
                'record_id':
                    self.env.ref('l10n_br_nfe.demo_nfe_natural_icms_18_resale'),
                'xml_file':
                    'NFe35210381583054000129550010000000011659437930-nf-e.xml',
            },
            {
                'record_id':
                    self.env.ref('l10n_br_nfe.demo_nfe_natural_icms_18_resale'),
                'xml_file':
                    'NFe35210381583054000129550010000000041662059365-nf-e.xml',
            },

        ]
