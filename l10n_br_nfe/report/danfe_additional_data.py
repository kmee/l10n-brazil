# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""DANFE with a configurable height for the "Dados Adicionais" block.

BrazilFiscalReport hardcodes 20 mm (5 lines) for the block on the first page
(a literal ``20`` inside ``_draw_additional_data`` of both layout classes), so
long infCpl/infAdFisco text spills into "CONTINUAÇÃO INFORMAÇÕES
COMPLEMENTARES" below the products.

Since 1.3, ``Danfe`` is a factory that returns ``DanfeMoc70`` or
``DanfeNt2026010``, so a subclass of ``Danfe`` does not work. We subclass both
concrete classes and pick one with the library's ``resolve_layout``.

The literal cannot be overridden without copying the method, so each subclass
carries a copy of ``_draw_additional_data`` (marked below) with the height
taken from ``self.additional_data_height``. To never print a wrong DANFE after
a library upgrade, the copies are only used when the library's own method has
exactly the source we copied (see ``_LIB_METHOD_SHA256``); otherwise
``get_danfe_class`` returns the stock ``Danfe`` and printing works as usual,
with the 20 mm block. Remove this module when DanfeConfig accepts the height.
"""
import hashlib
import inspect
import logging

_logger = logging.getLogger(__name__)

ADDITIONAL_DATA_HEIGHT_DEFAULT = 20

# sha256 (first 16 hex) of inspect.getsource(<lib class>._draw_additional_data)
# in BrazilFiscalReport 1.4.0, the version our copies were taken from.
_LIB_METHOD_SHA256 = {
    "DanfeMoc70": {"ad3645c3101fa489"},
    "DanfeNt2026010": {"b9675da634951c22"},
}


def _method_fingerprint(cls):
    source = inspect.getsource(cls._draw_additional_data)
    return hashlib.sha256(source.encode()).hexdigest()[:16]


def _build_classes():
    """Return {layout: subclass} or None if the library API is not the known one."""
    from brazilfiscalreport.danfe.danfe_block import DanfeBlock
    from brazilfiscalreport.danfe.danfe_conf import (
        HEIGHT_FONT_BLOCK_DESC,
        QR_CODE_BLOCK_GAP,
        QR_CODE_BLOCK_WIDTH,
        QR_CODE_BOX_SIZE,
    )
    from brazilfiscalreport.danfe.danfe_moc_7_0 import DanfeMoc70
    from brazilfiscalreport.danfe.danfe_nt_2026_010 import DanfeNt2026010
    from brazilfiscalreport.danfe.models import BaseFieldInfo

    for cls in (DanfeMoc70, DanfeNt2026010):
        if _method_fingerprint(cls) not in _LIB_METHOD_SHA256[cls.__name__]:
            return None

    class HeightMixin:
        # The library draws the whole PDF inside __init__, so the height must
        # be set before calling super().__init__().
        def __init__(
            self,
            xml,
            config=None,
            additional_data_height=ADDITIONAL_DATA_HEIGHT_DEFAULT,
        ):
            self.additional_data_height = additional_data_height
            super().__init__(xml, config=config)

    def _fields(additional_data, continuation_height):
        if not continuation_height:
            return [
                BaseFieldInfo(
                    w=0,
                    description="INFORMAÇÕES COMPLEMENTARES",
                    content=additional_data,
                    type="info_complementares",
                ),
                BaseFieldInfo(w=70, description="RESERVADO AO FISCO", content=""),
            ]
        return [
            BaseFieldInfo(
                w=0,
                description="CONTINUAÇÃO INFORMAÇÕES COMPLEMENTARES",
                content=additional_data,
            ),
        ]

    class Moc70(HeightMixin, DanfeMoc70):
        # COPY of DanfeMoc70._draw_additional_data (BrazilFiscalReport 1.4.0);
        # only change: `20` -> self.additional_data_height.
        def _draw_additional_data(self, additional_data, continuation_height=None):
            block_adic = DanfeBlock(description="DADOS ADICIONAIS", pdf=self)
            height = (
                continuation_height - HEIGHT_FONT_BLOCK_DESC
                if continuation_height
                else self.additional_data_height
            )
            block_adic.rows_heights = (height,)
            block_adic.add_fields([_fields(additional_data, continuation_height)])
            block_adic.render()
            add_data_field = block_adic.fields[0]
            return (
                add_data_field.get_content_lines(),
                add_data_field.get_max_content_lines(),
            )

    class Nt2026010(HeightMixin, DanfeNt2026010):
        # COPY of DanfeNt2026010._draw_additional_data (BrazilFiscalReport
        # 1.4.0, with the QR Code beside the block); only change: `20` ->
        # self.additional_data_height. Uses the private _draw_qr_code_block.
        def _draw_additional_data(self, additional_data, continuation_height=None):
            block_adic = DanfeBlock(description="DADOS ADICIONAIS", pdf=self)
            height = (
                continuation_height - HEIGHT_FONT_BLOCK_DESC
                if continuation_height
                else self.additional_data_height
            )
            draw_qr_code = self.qr_code_image is not None and not continuation_height
            if draw_qr_code:
                block_adic.w -= QR_CODE_BLOCK_WIDTH + QR_CODE_BLOCK_GAP
                height = max(height, QR_CODE_BOX_SIZE)
            block_adic.rows_heights = (height,)
            block_adic.add_fields([_fields(additional_data, continuation_height)])
            block_adic.render()
            if draw_qr_code:
                x_after, y_after = self.get_x(), self.get_y()
                self._draw_qr_code_block(
                    x=block_adic.x + block_adic.w + QR_CODE_BLOCK_GAP,
                    y=block_adic.y,
                    h=HEIGHT_FONT_BLOCK_DESC + height,
                )
                self.set_xy(x=x_after, y=y_after)
            add_data_field = block_adic.fields[0]
            return (
                add_data_field.get_content_lines(),
                add_data_field.get_max_content_lines(),
            )

    return {"moc_7_0": Moc70, "nt_2026_010": Nt2026010}


_CLASSES = {}


def _get_classes():
    if "classes" not in _CLASSES:
        try:
            _CLASSES["classes"] = _build_classes()
        except Exception:  # noqa: BLE001 - never break printing
            _logger.warning(
                "BrazilFiscalReport API differs from the expected one; "
                "DANFE additional data height will not be applied.",
                exc_info=True,
            )
            _CLASSES["classes"] = None
        if _CLASSES["classes"] is None:
            _logger.warning(
                "BrazilFiscalReport DANFE layout classes changed; using the "
                "stock Danfe (additional data block fixed at 20 mm)."
            )
    return _CLASSES["classes"]


def get_danfe_class(xml, config, height=ADDITIONAL_DATA_HEIGHT_DEFAULT):
    """Return ``(danfe_class, extra_kwargs)`` for the layout of this NF-e.

    Falls back to the stock ``Danfe`` (no extra kwargs) when the height is the
    default or the library API is not the one the overrides were written for.
    """
    from brazilfiscalreport.danfe import Danfe

    if not height or float(height) == ADDITIONAL_DATA_HEIGHT_DEFAULT:
        return Danfe, {}
    try:
        classes = _get_classes()
        if not classes:
            return Danfe, {}
        from brazilfiscalreport.danfe.danfe import resolve_layout

        layout = resolve_layout(xml, config.layout)
        key = "moc_7_0" if layout.name == "MOC_7_0" else "nt_2026_010"
        return classes[key], {"additional_data_height": height}
    except Exception:  # noqa: BLE001 - never break printing
        _logger.warning("Could not pick the DANFE class", exc_info=True)
        return Danfe, {}
