# Copyright 2020 KMEE INFORMATICA LTDA
#   Gabriel Cardoso de Faria <gabriel.cardoso@kmee.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
import os

from xmldiff import main

from odoo.tools import config

from odoo.addons.l10n_br_nfse.tests.test_fiscal_document_nfse_common import (
    TestFiscalDocumentNFSeCommon,
)

from ... import l10n_br_nfse_barueri

_logger = logging.getLogger(__name__)


class TestFiscalDocumentNFSeGinfes(TestFiscalDocumentNFSeCommon):
    def setUp(self):
        super(TestFiscalDocumentNFSeGinfes, self).setUp()

        self.company.provedor_nfse = "barueri"

    def test_nfse_barueri(self):
        """Test NFS-e same state."""

        xml_path = os.path.join(
            l10n_br_nfse_barueri.__path__[0], "tests", "nfse", "001_50_nfse.xml"
        )

        self.nfse_same_state.inscricao_municipal = "4492571"
        self.nfse_same_state.cpf_cnpj_contrib = "46523015000135"
        self.nfse_same_state.apenas_validar_arq = "false"

        self.nfse_same_state.with_context(lang="pt_BR")._document_export()

        output = os.path.join(
            config["data_dir"],
            "filestore",
            self.cr.dbname,
            self.nfse_same_state.send_file_id.store_fname,
        )
        _logger.info("XML file saved at %s" % (output,))

        diff = main.diff_files(xml_path, output)
        _logger.info("Diff with expected XML (if any): %s" % (diff,))

        assert len(diff) == 0

    def test_nfse_arquivo_base64_barueri(self):
        txt_path = os.path.join(
            l10n_br_nfse_barueri.__path__[0], "tests", "nfse", "arquivo_base64.txt"
        )
        output = os.path.join(
            # pega alguma coisa da lib
        )

        diff = main.diff_files(txt_path, output)
        assert len(diff) == 0
