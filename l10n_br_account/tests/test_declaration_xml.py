# Copyright 2026 KMEE (Ygor Carvalho <ygor.carvalho@kmee.com.br>)
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from datetime import date
from pathlib import Path
from xml.etree import ElementTree

from odoo.tests import TransactionCase

from ..wizards.declaration_xml import (
    DeclarationXmlError,
    parse_declaration,
    parse_txt_declaration,
    regime_signals,
    unmapped_tags,
)

FIXTURE = Path(__file__).parent / "fixtures" / "import_declaration.xml"
TXT_FIXTURE = Path(__file__).parent / "fixtures" / "import_declaration.txt"


class TestDeclarationXml(TransactionCase):
    """Reading the declaration the Siscomex hands out.

    The fixture keeps the shape of a declaration of two additions and carries
    made up identifiers and made up amounts, coherent among themselves: the
    Import Tax follows the base, the IPI follows the base plus the Import Tax,
    and the goods add up to the value of their addition. That coherence is what
    the reading is proved against, because every number in the file is an
    integer with the decimals implied and the implied place changes by field,
    so a wrong scale gives a plausible number that is off by a factor of ten.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.declaration = parse_declaration(FIXTURE.read_bytes())

    def test_the_header_comes_out_whole(self):
        self.assertEqual(self.declaration["number"], "2600000001")
        self.assertEqual(self.declaration["registration_date"], date(2026, 7, 10))
        self.assertEqual(self.declaration["clearance_date"], date(2026, 7, 10))
        self.assertEqual(self.declaration["transport_via"], "7")
        self.assertEqual(self.declaration["clearance_state"], "SP")

    def test_the_customs_value_is_the_sum_of_the_bases_of_the_import_tax(self):
        total = sum(a["customs_value"] for a in self.declaration["additions"])
        self.assertAlmostEqual(total, 800000.00, places=2)

    def test_each_addition_keeps_its_own_rate(self):
        """The point of reading addition by addition: the rate changes."""
        by_number = {a["number"]: a for a in self.declaration["additions"]}
        self.assertEqual(by_number["001"]["ncm"], "8414.90.20")
        self.assertAlmostEqual(by_number["001"]["ii_rate"], 12.60, places=2)
        self.assertAlmostEqual(by_number["001"]["ipi_rate"], 3.25, places=2)
        self.assertEqual(by_number["002"]["ncm"], "8537.10.90")
        self.assertAlmostEqual(by_number["002"]["ii_rate"], 18.00, places=2)
        self.assertAlmostEqual(by_number["002"]["ipi_rate"], 9.75, places=2)

    def test_the_import_tax_of_an_addition_follows_its_base_and_rate(self):
        """Coherence of the fixture, and of any declaration: the amount charged
        is the base times the rate the addition carries."""
        for addition in self.declaration["additions"]:
            self.assertAlmostEqual(
                addition["ii_value"],
                addition["customs_value"] * addition["ii_rate"] / 100.0,
                places=2,
            )

    def test_the_tax_of_the_additions_adds_up_to_the_declaration(self):
        additions = self.declaration["additions"]
        self.assertAlmostEqual(
            sum(a["ii_value"] for a in additions), 141840.00, places=2
        )
        self.assertAlmostEqual(
            sum(a["ipi_value"] for a in additions), 88901.80, places=2
        )
        self.assertAlmostEqual(
            sum(a["pis_value"] for a in additions), 16800.00, places=2
        )
        self.assertAlmostEqual(
            sum(a["cofins_value"] for a in additions), 77200.00, places=2
        )
        self.assertAlmostEqual(self.declaration["icms_value"], 200000.00, places=2)

    def test_the_goods_of_an_addition_add_up_to_its_value_in_currency(self):
        """Quantity and unit value carry different scales, five and seven.

        Reading either with the scale of money gives a total that is off by
        orders of magnitude, and nothing else in the file catches it.
        """
        addition = self.declaration["additions"][0]
        total = sum(i["quantity"] * i["unit_value"] for i in addition["items"])
        self.assertAlmostEqual(total, 8000.00, places=2)

    def test_the_ncm_comes_out_the_way_the_catalog_writes_it(self):
        self.assertEqual(self.declaration["additions"][0]["ncm"], "8414.90.20")

    def test_the_description_loses_the_tail_the_siscomex_glues_to_it(self):
        description = self.declaration["additions"][0]["items"][0]["description"]
        self.assertNotIn("cClassTrib", description)
        self.assertNotIn("\r", description)
        self.assertEqual(description, "MERCADORIA 1 DA ADICAO 1")

    def test_the_weight_is_read_with_its_own_scale(self):
        self.assertAlmostEqual(self.declaration["net_weight"], 180.00, places=2)

    def test_a_file_that_is_not_a_declaration_is_refused(self):
        with self.assertRaises(DeclarationXmlError):
            parse_declaration(b"<outraCoisa><a/></outraCoisa>")

    def test_a_file_that_is_not_xml_is_refused(self):
        with self.assertRaises(DeclarationXmlError):
            parse_declaration(b"nao sou xml")

    def test_the_declaration_reports_the_tags_it_ignores(self):
        self.assertIn("importadorNome", self.declaration["unmapped_tags"])
        self.assertNotIn("numeroDI", self.declaration["unmapped_tags"])
        self.assertNotIn("adicao", self.declaration["unmapped_tags"])

    def test_a_file_with_nothing_extra_reports_no_unmapped_tags(self):
        root = ElementTree.fromstring(
            "<declaracaoImportacao><numeroDI>0000000001</numeroDI>"
            "</declaracaoImportacao>"
        )
        self.assertEqual(unmapped_tags(root), [])

    def test_each_addition_carries_its_own_regime_codes(self):
        addition = self.declaration["additions"][0]
        self.assertEqual(addition["ii_regime_code"], "1")
        self.assertEqual(addition["ipi_regime_code"], "4")
        self.assertEqual(addition["pis_cofins_regime_code"], "1")

    def test_each_addition_carries_its_own_exporter_and_incoterm(self):
        addition = self.declaration["additions"][0]
        self.assertEqual(addition["exporter"], "FORNECEDOR DO EXTERIOR")
        self.assertEqual(addition["incoterm"], "FCA")

    def test_a_drawback_act_of_all_zeroes_is_not_a_drawback(self):
        addition = self.declaration["additions"][0]
        self.assertEqual(addition["drawback_act"], "")

    def test_the_operation_type_code_comes_out_of_the_header(self):
        self.assertEqual(self.declaration["operation_type_code"], "1")


class TestRealShapedDeclaration(TransactionCase):
    """A DI actually issued for an import, with the identifying fields
    swapped for made up ones and the fiscal numbers kept as they were
    charged.
    """

    FIXTURE = (
        Path(__file__).parent / "fixtures" / "import_declaration_multi_addition.xml"
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.declaration = parse_declaration(cls.FIXTURE.read_bytes())

    def test_it_reads_every_addition(self):
        self.assertEqual(len(self.declaration["additions"]), 7)

    def test_it_carries_no_identifying_field(self):
        self.assertNotIn("47786619000137", self.declaration["importer_document"])

    def test_it_signals_no_regime_the_file_does_not_state(self):
        self.assertEqual(self.declaration["regime_signals"], [])

    def test_every_addition_shares_the_same_ncm_and_exporter(self):
        ncms = {a["ncm"] for a in self.declaration["additions"]}
        exporters = {a["exporter"] for a in self.declaration["additions"]}
        self.assertEqual(ncms, {"8414.90.20"})
        self.assertEqual(exporters, {"FORNECEDOR DE TESTE S.A."})


class TestRegimeSignals(TransactionCase):
    def _root(self, body):
        return ElementTree.fromstring(
            f"<declaracaoImportacao>{body}</declaracaoImportacao>"
        )

    def test_the_common_regime_code_raises_no_signal(self):
        root = self._root(
            "<adicao><iiRegimeTributacaoCodigo>1</iiRegimeTributacaoCodigo></adicao>"
        )
        self.assertEqual(regime_signals(root), [])

    def test_a_different_regime_code_is_flagged(self):
        root = self._root(
            "<adicao><iiRegimeTributacaoCodigo>3</iiRegimeTributacaoCodigo></adicao>"
        )
        self.assertEqual(
            regime_signals(root),
            ["II sob regime de tributação diferente do comum"],
        )

    def test_a_rectified_declaration_is_flagged(self):
        root = self._root("<numeroRetificacao>01</numeroRetificacao>")
        self.assertEqual(regime_signals(root), ["DI retificada"])

    def test_an_unrectified_declaration_raises_no_signal(self):
        root = self._root("<numeroRetificacao>00</numeroRetificacao>")
        self.assertEqual(regime_signals(root), [])

    def test_drawback_is_flagged(self):
        root = self._root(
            "<adicao><dcrIdentificacao>12345678</dcrIdentificacao></adicao>"
        )
        self.assertEqual(regime_signals(root), ["drawback"])


class TestTxtDeclaration(TransactionCase):
    """Reading the despachante's draft-invoice TXT.

    The fixture holds two real additions, 001 and 002, at different Import
    Tax rates (12.60% and 18.00%), with 001 split across two `H` blocks that
    are not adjacent in the file — the third block belongs back to 001, after
    a block of 002. Every `I18` record repeats the same transport mode in its
    field 6, which is the value the reader used to mistake for the addition
    number: if that field decided the grouping, every block would collapse
    into one addition instead of two.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.declaration = parse_txt_declaration(TXT_FIXTURE.read_bytes())

    def test_the_transport_mode_does_not_decide_the_grouping(self):
        additions = self.declaration["additions"]
        self.assertEqual(len(additions), 2)
        self.assertEqual({a["number"] for a in additions}, {"001", "002"})

    def test_addition_one_zero_zero_one_merges_its_two_blocks(self):
        by_number = {a["number"]: a for a in self.declaration["additions"]}
        addition = by_number["001"]
        self.assertEqual(len(addition["items"]), 2)
        self.assertAlmostEqual(addition["customs_value"], 100000.00, places=2)
        self.assertAlmostEqual(addition["ii_value"], 12600.00, places=2)
        self.assertAlmostEqual(addition["ii_rate"], 12.60, places=2)

    def test_addition_zero_zero_two_stays_on_its_own(self):
        by_number = {a["number"]: a for a in self.declaration["additions"]}
        addition = by_number["002"]
        self.assertEqual(len(addition["items"]), 1)
        self.assertAlmostEqual(addition["customs_value"], 50000.00, places=2)
        self.assertAlmostEqual(addition["ii_value"], 9000.00, places=2)
        self.assertAlmostEqual(addition["ii_rate"], 18.00, places=2)

    def test_the_import_tax_of_each_addition_follows_its_own_base_and_rate(self):
        for addition in self.declaration["additions"]:
            self.assertAlmostEqual(
                addition["ii_value"],
                addition["customs_value"] * addition["ii_rate"] / 100.0,
                places=2,
            )

    def test_ipi_pis_and_cofins_stay_with_their_own_addition(self):
        by_number = {a["number"]: a for a in self.declaration["additions"]}
        self.assertAlmostEqual(by_number["001"]["ipi_value"], 3660.50, places=2)
        self.assertAlmostEqual(by_number["001"]["pis_value"], 2100.00, places=2)
        self.assertAlmostEqual(by_number["001"]["cofins_value"], 9650.00, places=2)
        self.assertAlmostEqual(by_number["002"]["ipi_value"], 5752.50, places=2)
        self.assertAlmostEqual(by_number["002"]["pis_value"], 1050.00, places=2)
        self.assertAlmostEqual(by_number["002"]["cofins_value"], 4825.00, places=2)

    def test_the_file_reports_the_records_it_ignores(self):
        unmapped = self.declaration["unmapped_tags"]
        for tag in ("A", "B", "C", "C05", "E03a", "M", "N", "O", "Q", "S"):
            self.assertIn(tag, unmapped)
        for tag in ("C02", "E", "H", "I", "I18", "I25", "N02", "O07", "O10", "P"):
            self.assertNotIn(tag, unmapped)

    def test_the_tax_of_the_additions_adds_up_to_the_file(self):
        additions = self.declaration["additions"]
        self.assertAlmostEqual(
            sum(a["ipi_value"] for a in additions), 9413.00, places=2
        )
        self.assertAlmostEqual(
            sum(a["pis_value"] for a in additions), 3150.00, places=2
        )
        self.assertAlmostEqual(
            sum(a["cofins_value"] for a in additions), 14475.00, places=2
        )

    def test_the_txt_never_states_a_regime_code(self):
        for addition in self.declaration["additions"]:
            self.assertEqual(addition["ii_regime_code"], "")
            self.assertEqual(addition["ipi_regime_code"], "")
            self.assertEqual(addition["pis_cofins_regime_code"], "")
            self.assertEqual(addition["drawback_act"], "")
            self.assertEqual(addition["incoterm"], "")
        self.assertEqual(self.declaration["operation_type_code"], "")
