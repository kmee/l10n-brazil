# @ 2020 KMEE INFORMATICA LTDA - www.kmee.com.br -
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from .test_nfe_serialize import TestNFeExport


class TestNFeExportLC(TestNFeExport):
    def setUp(self):
        super().setUp()

        company_id = self.env.ref('l10n_br_base.empresa_simples_nacional')
        company_id.certificate_nfe_id = self.cert

        self.nfe_list = [
            {
                'record_id':
                    self.env.ref(
                        'l10n_br_nfe.demo_nfe_national_sale_for_same_state'),
                'xml_file':
                    'NFe35210359594315000157550010000000011291881715-nf-e.xml',
            },
        ]
