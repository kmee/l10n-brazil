# @ 2020 KMEE INFORMATICA LTDA - www.kmee.com.br -
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import logging

from erpbrasil.edoc.nfe import NFe

from .test_nfe_serialize import TestNFeExport

_logger = logging.getLogger(__name__)


class TestNFeExportSN(TestNFeExport):
    def setUp(self):
        nfe_list = [
            {
                "record_ref": "l10n_br_nfe.demo_nfe_national_sale_for_same_state",
                "xml_file": "NFe35200159594315000157550010000000012062777161.xml",
            },
        ]
        super().setUp(nfe_list)

    def test_serialize_xml(self):
        for nfe_data in self.nfe_list:
            nfe = nfe_data["nfe"]
            diff = self.serialize_xml(nfe_data)
            _logger.info("Diff with expected XML (if any): %s" % (diff,))

            assert len(diff) == 0
            assert nfe.nfe40_dhSaiEnt == nfe.date_in_out
            assert isinstance(nfe._processador(), NFe)
