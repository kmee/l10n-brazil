# Copyright 2024 Engenere.one
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import re
from datetime import datetime, timezone
from unittest.mock import patch

from brazilfiscalreport.danfe import Danfe, DanfeConfig
from brazilfiscalreport.danfe.config import DanfeLayout
from brazilfiscalreport.danfe.danfe import resolve_layout
from brazilfiscalreport.danfe.danfe_moc_7_0 import DanfeMoc70
from brazilfiscalreport.danfe.danfe_nt_2026_010 import DanfeNt2026010

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

from ..report import danfe_additional_data

FIXED_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)


class TestDanfeGeneration(TransactionCase):
    def test_generate_danfe_brazil_fiscal_report(self):
        nfe = self.env.ref("l10n_br_nfe.demo_nfe_natural_icms_18_red_51_11")
        nfe.action_document_confirm()
        nfe.view_pdf()
        self.assertTrue(nfe.file_report_id)

    def test_generate_danfe_document_type_error(self):
        danfe_report = self.env["ir.actions.report"].search(
            [("report_name", "=", "main_template_danfe")]
        )
        nfe = self.env.ref("l10n_br_nfe.demo_nfe_natural_icms_18_red_51_11")
        nfe.document_type_id = self.env.ref("l10n_br_fiscal.document_01")
        nfe.action_document_confirm()
        with self.assertRaises(UserError) as captured_exception:
            danfe_report._render_qweb_pdf("main_template_danfe", [nfe.id])
        self.assertEqual(
            captured_exception.exception.args[0],
            "You can only print a DANFE of a NFe(55).",
        )

    def test_generate_danfe_brazil_fiscal_report_partner(self):
        nfe = self.env.ref("l10n_br_nfe.demo_nfe_natural_icms_18_red_51_11")
        nfe.action_document_confirm()
        nfe.issuer = "partner"
        nfe.view_pdf()
        self.assertTrue(nfe.file_report_id)

    def test_generate_danfe_after_authorization(self):
        """The DANFE must be generated automatically upon authorization.

        Regression test: the legacy _exec_after_SITUACAO_EDOC_AUTORIZADA
        hook that generated it became dead code with the FSM refactor.
        """
        nfe = self.env.ref("l10n_br_nfe.demo_nfe_natural_icms_18_red_51_11")
        nfe.action_document_confirm()
        self.assertFalse(nfe.file_report_id)
        nfe._trigger_fsm("action_authorize")
        self.assertTrue(nfe.file_report_id)


class TestDanfeAdditionalDataHeight(TransactionCase):
    # Roughly the NF-e 817 case: infCpl (~270 chars) + infAdFisco (~260 chars)
    # Needs 6 lines: more than the 5 of 20 mm, within the 9 of 30.7 mm.
    INF_CPL = "Remessa de venda para entrega futura conforme pedido e contrato. " * 6
    INF_FISCO = "Informacao de interesse do fisco sobre a operacao. " * 6

    def setUp(self):
        super().setUp()
        danfe_additional_data._CLASSES.clear()
        self.addCleanup(danfe_additional_data._CLASSES.clear)
        nfe = self.env.ref("l10n_br_nfe.demo_nfe_natural_icms_18_red_51_11")
        nfe.action_document_confirm()
        self.nfe = nfe
        xml = base64.b64decode(nfe.send_file_id.datas).decode()
        info = "<infAdic><infAdFisco>%s</infAdFisco><infCpl>%s</infCpl></infAdic>" % (
            self.INF_FISCO,
            self.INF_CPL,
        )
        if "<infAdic>" in xml:
            xml = re.sub(r"<infAdic>.*?</infAdic>", info, xml, flags=re.S)
        else:
            xml = xml.replace("</infNFe>", info + "</infNFe>", 1)
        self.xml = xml.encode()
        self.config = DanfeConfig()

    def _render(self, height, config):
        """Return (danfe, first page additional data (lines, max lines))."""
        cls, extra = danfe_additional_data.get_danfe_class(self.xml, config, height)
        if cls is Danfe:  # the factory cannot be subclassed: use the real class
            cls = (
                DanfeMoc70
                if resolve_layout(self.xml, config.layout) == DanfeLayout.MOC_7_0
                else DanfeNt2026010
            )
        first_page = []

        class Recorder(cls):
            def _draw_additional_data(self_, text, continuation_height=None):
                lines, max_lines = super()._draw_additional_data(
                    text, continuation_height=continuation_height
                )
                if not continuation_height and not first_page:
                    first_page.extend([len(lines), max_lines])
                return lines, max_lines

        danfe = Recorder(xml=self.xml, config=config, **extra)
        return danfe, first_page

    def test_default_height_field(self):
        self.assertEqual(self.env.company.danfe_additional_data_height, 20)

    def test_height_limits(self):
        for value in (19.9, 60.1):
            with self.assertRaises(ValidationError):
                self.env.company.danfe_additional_data_height = value
        self.env.company.danfe_additional_data_height = 30.7
        self.assertEqual(self.env.company.danfe_additional_data_height, 30.7)

    def test_default_height_uses_stock_danfe(self):
        cls, extra = danfe_additional_data.get_danfe_class(self.xml, self.config, 20)
        self.assertIs(cls, Danfe)
        self.assertFalse(extra)

    def test_height_20_same_output_as_stock(self):
        """The copied methods with 20 mm must draw exactly what the lib draws."""
        classes = danfe_additional_data._get_classes()
        self.assertTrue(classes, "BrazilFiscalReport API not the expected one")
        for key, cls in classes.items():
            layout = "MOC_7_0" if key == "moc_7_0" else "NT_2026_010"
            config = DanfeConfig(layout=getattr(DanfeLayout, layout))
            stock = Danfe(xml=self.xml, config=config)
            custom = cls(xml=self.xml, config=config, additional_data_height=20)
            self.assertIs(type(stock).__mro__[0], cls.__mro__[2])
            stock.creation_date = custom.creation_date = FIXED_DATE
            self.assertEqual(
                bytes(stock.output()), bytes(custom.output()), "layout %s" % key
            )

    def test_taller_block_fits_text_in_footer(self):
        for layout in (DanfeLayout.MOC_7_0, DanfeLayout.NT_2026_010):
            config = DanfeConfig(layout=layout)
            _danfe, (lines, max_lines) = self._render(20, config)
            self.assertGreater(
                lines, max_lines, "%s: 20 mm must spill below the items" % layout
            )
            _danfe, (lines, max_lines) = self._render(30.7, config)
            self.assertLessEqual(
                lines, max_lines, "%s: 30.7 mm must fit the footer" % layout
            )

    def test_layout_picked_by_resolve_layout(self):
        for layout in ("MOC_7_0", "NT_2026_010"):
            config = DanfeConfig(layout=getattr(DanfeLayout, layout))
            cls, extra = danfe_additional_data.get_danfe_class(self.xml, config, 30.7)
            stock = type(Danfe(xml=self.xml, config=config))
            self.assertTrue(issubclass(cls, stock))
            self.assertEqual(extra, {"additional_data_height": 30.7})

    def test_unknown_lib_api_falls_back_to_stock(self):
        with patch.dict(
            danfe_additional_data._LIB_METHOD_SHA256,
            {"DanfeMoc70": set(), "DanfeNt2026010": set()},
        ):
            cls, extra = danfe_additional_data.get_danfe_class(
                self.xml, self.config, 30.7
            )
        self.assertIs(cls, Danfe)
        self.assertFalse(extra)

    def test_missing_lib_module_falls_back_to_stock(self):
        with patch.object(
            danfe_additional_data, "_build_classes", side_effect=ImportError("x")
        ):
            cls, extra = danfe_additional_data.get_danfe_class(
                self.xml, self.config, 30.7
            )
        self.assertIs(cls, Danfe)
        self.assertFalse(extra)

    def test_render_falls_back_when_custom_class_fails(self):
        class Broken:
            def __init__(self, *args, **kwargs):
                raise TypeError("unexpected keyword argument")

        self.nfe.company_id.danfe_additional_data_height = 30.7
        with patch(
            "odoo.addons.l10n_br_nfe.report.ir_actions_report.get_danfe_class",
            return_value=(Broken, {"additional_data_height": 30.7}),
        ):
            self.nfe.view_pdf()
        self.assertTrue(self.nfe.file_report_id)

    def test_company_height_is_used_in_render(self):
        self.nfe.company_id.danfe_additional_data_height = 30.7
        with patch(
            "odoo.addons.l10n_br_nfe.report.ir_actions_report.get_danfe_class",
            wraps=danfe_additional_data.get_danfe_class,
        ) as get_class:
            self.nfe.view_pdf()
        self.assertEqual(get_class.call_args.args[2], 30.7)
