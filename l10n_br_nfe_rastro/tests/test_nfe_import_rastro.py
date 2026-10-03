# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import importlib.resources
from datetime import date

import nfelib
from nfelib.nfe.bindings.v4_0.leiaute_nfe_v4_00 import TnfeProc

from odoo.tests import TransactionCase

SAMPLE = (
    "nfe",
    "samples",
    "v4_0",
    "leiauteNFe",
    "35180834128745000152550010000474281920007498-nfe.xml",
)

RASTRO = (
    "<rastro><nLote>L1</nLote><qLote>4.000</qLote>"
    "<dFab>2018-01-15</dFab><dVal>2019-01-31</dVal></rastro>"
    "<rastro><nLote>L2</nLote><qLote>2.000</qLote>"
    "<dFab>2018-02-01</dFab><dVal>2019-02-28</dVal>"
    "<cAgreg>AGG-9</cAgreg></rastro>"
)


class TestNFeImportRastro(TransactionCase):
    def test_import_supplier_nfe_with_rastro(self):
        """The lots of an incoming NF-e are kept on the imported line."""
        xml = (
            importlib.resources.files(nfelib.__name__)
            .joinpath(*SAMPLE)
            .read_bytes()
            .decode()
        )
        # the first item gets two lots (<rastro> is the last tag of <prod>
        # in the sample, as allowed by the schema sequence)
        xml = xml.replace(
            "<indTot>1</indTot>\n        </prod>",
            f"<indTot>1</indTot>{RASTRO}</prod>",
            1,
        )
        self.assertIn("<nLote>L1</nLote>", xml)
        binding = TnfeProc.from_xml(xml)
        document = self.env["l10n_br_fiscal.document"].import_binding_nfe(
            binding, edoc_type="in", dry_run=False
        )
        line = document.fiscal_line_ids.filtered(lambda ln: ln.nfe40_cProd == "1208")
        self.assertEqual(len(line), 1)
        self.assertEqual(
            sorted(
                (
                    r.nfe40_nLote,
                    r.nfe40_qLote,
                    r.nfe40_dFab,
                    r.nfe40_dVal,
                    r.nfe40_cAgreg,
                )
                for r in line.nfe40_rastro
            ),
            [
                ("L1", 4.0, date(2018, 1, 15), date(2019, 1, 31), False),
                ("L2", 2.0, date(2018, 2, 1), date(2019, 2, 28), "AGG-9"),
            ],
        )
        others = document.fiscal_line_ids - line
        self.assertFalse(others.nfe40_rastro)
