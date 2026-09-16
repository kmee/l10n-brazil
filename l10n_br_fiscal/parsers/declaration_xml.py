# Copyright 2026 KMEE (Ygor Carvalho <ygor.carvalho@kmee.com.br>)
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
"""Reader of the import declaration XML that the Siscomex hands out.

Kept free of Odoo on purpose: the shape of the file is the whole difficulty
here, and a plain function over bytes can be exercised without a database.

Every number in the file is an integer with the decimals implied, and the
implied place changes by field: money and rates carry two, quantity carries
five, unit value carries seven. Reading a value with the wrong scale gives a
number that looks plausible and is off by a factor of ten, so the scale lives
next to each field instead of being guessed at the call site.
"""

import re
from datetime import date
from xml.etree import ElementTree

MONEY = 2
RATE = 2
QUANTITY = 5
UNIT_VALUE = 7
WEIGHT = 5


class DeclarationXmlError(ValueError):
    """The file is not an import declaration this reader understands."""


class DeclarationParseError(DeclarationXmlError):
    """A field of the declaration does not hold the value its record promises.

    Names the record, the field and the raw value so whoever reads the
    message can go straight to the line that needs fixing, instead of a bare
    traceback pointing at a cast three layers removed from the file.
    """

    def __init__(self, record, field, raw_value, line_number=None):
        self.record = record
        self.field = field
        self.raw_value = raw_value
        self.line_number = line_number
        where = f"record {record}"
        if line_number is not None:
            where += f", line {line_number}"
        super().__init__(
            f"{where}, field {field}: {raw_value!r} is not a number in the "
            "layout's format."
        )


def _number(element, scale):
    if element is None or not (element.text or "").strip():
        return 0.0
    raw = element.text.strip()
    try:
        return int(raw) / (10**scale)
    except ValueError as error:
        raise DeclarationParseError(
            record=element.tag, field=element.tag, raw_value=raw
        ) from error


def _text(parent, tag):
    element = parent.find(tag)
    return (element.text or "").strip() if element is not None else ""


def _amount(parent, tag, scale=MONEY):
    return _number(parent.find(tag), scale)


def _date(parent, tag):
    raw = _text(parent, tag)
    if len(raw) != 8 or not raw.isdigit():
        return False
    return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))


def _ncm(raw):
    """The file writes the NCM without the dots the catalog uses."""
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) != 8:
        return raw
    return f"{digits[:4]}.{digits[4:6]}.{digits[6:]}"


def _description(raw):
    """The description of the item, without the tail the Siscomex glues to it.

    The classification code travels inside the description as `cClassTrib=[...]`,
    and the field comes padded with spaces and carriage returns.
    """
    text = raw.replace("\r", " ")
    marker = text.find("cClassTrib=")
    if marker >= 0:
        text = text[:marker]
    return " ".join(text.split())


def _items(addition):
    items = []
    for item in addition.findall("mercadoria"):
        items.append(
            {
                "sequence": _text(item, "numeroSequencialItem"),
                "description": _description(_text(item, "descricaoMercadoria")),
                "quantity": _amount(item, "quantidade", QUANTITY),
                "unit_value": _amount(item, "valorUnitario", UNIT_VALUE),
                "uom": _text(item, "unidadeMedida").strip(),
            }
        )
    return items


def _drawback_act(addition):
    value = _text(addition, "dcrIdentificacao")
    return value if value.strip("0") else ""


def _additions(declaration):
    additions = []
    for addition in declaration.findall("adicao"):
        additions.append(
            {
                "number": _text(addition, "numeroAdicao"),
                "ncm": _ncm(_text(addition, "dadosMercadoriaCodigoNcm")),
                # The base of the Import Tax is the customs value of the
                # addition: the goods plus the freight and the insurance that
                # the file already spread over the additions.
                "customs_value": _amount(addition, "iiBaseCalculo"),
                "goods_value": _amount(addition, "condicaoVendaValorReais"),
                "ii_rate": _amount(addition, "iiAliquotaAdValorem", RATE),
                "ii_value": _amount(addition, "iiAliquotaValorRecolher"),
                "ii_regime_code": _text(addition, "iiRegimeTributacaoCodigo"),
                "ipi_rate": _amount(addition, "ipiAliquotaAdValorem", RATE),
                "ipi_value": _amount(addition, "ipiAliquotaValorRecolher"),
                "ipi_regime_code": _text(addition, "ipiRegimeTributacaoCodigo"),
                "pis_rate": _amount(addition, "pisPasepAliquotaAdValorem", RATE),
                "pis_value": _amount(addition, "pisPasepAliquotaValorRecolher"),
                "cofins_value": _amount(addition, "cofinsAliquotaValorRecolher"),
                "pis_cofins_regime_code": _text(
                    addition, "pisCofinsRegimeTributacaoCodigo"
                ),
                "net_weight": _amount(addition, "dadosMercadoriaPesoLiquido", WEIGHT),
                "exporter": _text(addition, "fornecedorNome"),
                "manufacturer": _text(addition, "fabricanteNome"),
                "origin_country": _text(addition, "paisOrigemMercadoriaNome"),
                "incoterm": _text(addition, "condicaoVendaIncoterm"),
                "drawback_act": _drawback_act(addition),
                "items": _items(addition),
            }
        )
    return additions


SISCOMEX_REVENUE_CODE = "7811"


def _customhouse_charges(declaration):
    return sum(
        _amount(pagamento, "valorReceita")
        for pagamento in declaration.findall("pagamento")
        if _text(pagamento, "codigoReceita") == SISCOMEX_REVENUE_CODE
    )


STRUCTURAL_TAGS = {
    "ListaDeclaracoes",
    "declaracaoImportacao",
    "icms",
    "pagamento",
    "adicao",
    "mercadoria",
}

MAPPED_TAGS = STRUCTURAL_TAGS | {
    "numeroDI",
    "dataRegistro",
    "dataDesembaraco",
    "viaTransporteCodigo",
    "armazenamentoRecintoAduaneiroNome",
    "cargaUrfEntradaNome",
    "importadorNumero",
    "freteTotalReais",
    "seguroTotalReais",
    "cargaPesoBruto",
    "cargaPesoLiquido",
    "ufIcms",
    "valorTotalIcms",
    "codigoReceita",
    "valorReceita",
    "numeroAdicao",
    "dadosMercadoriaCodigoNcm",
    "iiBaseCalculo",
    "condicaoVendaValorReais",
    "iiAliquotaAdValorem",
    "iiAliquotaValorRecolher",
    "ipiAliquotaAdValorem",
    "ipiAliquotaValorRecolher",
    "pisPasepAliquotaAdValorem",
    "pisPasepAliquotaValorRecolher",
    "cofinsAliquotaValorRecolher",
    "dadosMercadoriaPesoLiquido",
    "fornecedorNome",
    "fabricanteNome",
    "paisOrigemMercadoriaNome",
    "numeroSequencialItem",
    "descricaoMercadoria",
    "quantidade",
    "valorUnitario",
    "unidadeMedida",
    "iiRegimeTributacaoCodigo",
    "ipiRegimeTributacaoCodigo",
    "pisCofinsRegimeTributacaoCodigo",
    "dcrIdentificacao",
    "condicaoVendaIncoterm",
    "caracterizacaoOperacaoCodigoTipo",
}


def unmapped_tags(root):
    present = {element.tag for element in root.iter()}
    return sorted(present - MAPPED_TAGS)


NORMAL_REGIME_CODE = "1"
IPI_NORMAL_REGIME_CODE = "4"

REGIME_SIGNALS = {
    "iiRegimeTributacaoCodigo": (
        (
            "II sob regime de tributação diferente do comum "
            "(tabela de códigos não confirmada, todo código não-zero é sinalizado)"
        ),
        set(),
    ),
    "iiAliquotaReduzida": ("alíquota de II reduzida", set()),
    "iiAcordoTarifarioTipoCodigo": ("II sob acordo tarifário", set()),
    "iiMotivoAdmissaoTemporariaCodigo": ("admissão temporária", set()),
    "dcrIdentificacao": ("drawback", set()),
    "numeroRetificacao": ("DI retificada", set()),
    "destaqueNcm": ("ex-tarifário", set()),
    "ipiRegimeTributacaoCodigo": (
        "IPI sob regime de tributação diferente do comum",
        {IPI_NORMAL_REGIME_CODE},
    ),
    "pisCofinsRegimeTributacaoCodigo": (
        (
            "PIS/COFINS sob regime de tributação diferente do comum "
            "(tabela de códigos não confirmada, todo código não-zero é sinalizado)"
        ),
        set(),
    ),
    "caracterizacaoOperacaoCodigoTipo": (
        "importação por conta e ordem ou por encomenda",
        {NORMAL_REGIME_CODE},
    ),
}


def regime_signals(root):
    found = set()
    for tag, (label, trivial_values) in REGIME_SIGNALS.items():
        for element in root.iter(tag):
            value = (element.text or "").strip()
            if not value or value in trivial_values:
                continue
            if not value.strip("0"):
                continue
            found.add(label)
            break
    return sorted(found)


def parse_declaration(content):
    """Turn the XML of one import declaration into plain data.

    Returns the header of the declaration and its additions, each with its own
    NCM, its own rates and the goods it covers. The additions are the point:
    the tax the declaration charged changes from one to the next, and a single
    total spread by weight over the whole note cannot reproduce it.
    """
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as error:
        raise DeclarationXmlError(f"The file is not valid XML: {error}") from error

    declaration = root if root.tag == "declaracaoImportacao" else None
    if declaration is None:
        declaration = root.find("declaracaoImportacao")
    if declaration is None:
        raise DeclarationXmlError(
            "No declaracaoImportacao in the file. The expected one is the XML "
            "the Siscomex hands out for the import declaration."
        )

    icms = declaration.find("icms")
    return {
        "number": _text(declaration, "numeroDI"),
        "registration_date": _date(declaration, "dataRegistro"),
        "clearance_date": _date(declaration, "dataDesembaraco"),
        "transport_via": _text(declaration, "viaTransporteCodigo").lstrip("0"),
        "clearance_place": _text(declaration, "armazenamentoRecintoAduaneiroNome")
        or _text(declaration, "cargaUrfEntradaNome"),
        "clearance_state": _text(icms, "ufIcms") if icms is not None else "",
        "importer_document": _text(declaration, "importadorNumero"),
        "operation_type_code": _text(declaration, "caracterizacaoOperacaoCodigoTipo"),
        "freight": _amount(declaration, "freteTotalReais"),
        "insurance": _amount(declaration, "seguroTotalReais"),
        "icms_value": _amount(icms, "valorTotalIcms") if icms is not None else 0.0,
        "customhouse_charges": _customhouse_charges(declaration),
        # The Siscomex XML never states this on its own: AFRMM is a payment
        # to a different fund, not a customs charge of the DI itself. Left at
        # 0.0 here on purpose, so a maritime import through this reader still
        # needs the operator to type it once — the TXT reader below does not.
        "afrmm": 0.0,
        "gross_weight": _amount(declaration, "cargaPesoBruto", WEIGHT),
        "net_weight": _amount(declaration, "cargaPesoLiquido", WEIGHT),
        "additions": _additions(declaration),
        "unmapped_tags": unmapped_tags(root),
        "regime_signals": regime_signals(root),
    }


def _brl_to_float(raw):
    """"1.705,10" the way the despachante writes it, not "1705.10"."""
    return float(raw.replace(".", "").replace(",", "."))


def _txt_field(parts, index, default=""):
    return parts[index].strip() if index < len(parts) else default


def _txt_number(parts, index, record, field, line_number, default=0.0):
    """A numeric field of a TXT record, or a named error, never a bare crash.

    An empty field is 0.0 — the despachante leaves a column blank rather than
    typing a zero. Anything else that fails to parse names the record, the
    line and the field: a broker's extra or reshuffled column shows up here
    as a clear message, not a traceback three layers removed from the file.
    """
    raw = _txt_field(parts, index)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as error:
        raise DeclarationParseError(
            record=record, field=field, raw_value=raw, line_number=line_number
        ) from error


# Every record tag actually seen, letters or digits, of any length: this only
# decides what counts as "a tag" for the unmapped-fields report, never what
# gets parsed. A record this reader has no branch for must still be visible
# there instead of vanishing because its name does not fit an assumed shape.
TXT_TAG_PATTERN = re.compile(r"^[A-Za-z0-9]+$")

TXT_MAPPED_TAGS = {
    "C02",
    "E",
    "E05",
    "H",
    "I",
    "I18",
    "I25",
    "N02",
    "O07",
    "O10",
    "P",
    "Q02",
    "S02",
    "Z",
}


def _txt_date(raw):
    raw = (raw or "").strip()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return False


def parse_txt_declaration(content):
    """Turn the despachante's draft-invoice TXT into the same plain data
    `parse_declaration` returns from the Siscomex XML.

    The DI itself never states the Import Tax per addition on paper — the
    despachante already worked it out here, item by item, precisely because
    nobody types nine tariff lines by hand. One line per record, fields
    separated by "|": `H` opens an item block, `I` carries the item, `I18`
    carries the DI reference (field 6 is `tpViaTransp`, the transport mode,
    not the addition), `I25` carries the addition number itself (field 1,
    `nAdicao` — field 2 is only the item's sequence inside it), `N02` is the
    ICMS, `O07`+`O10` the IPI, `P` the Import Tax (base at position 1, value
    at position 3), `Q02` the PIS, `S02` the COFINS.

    A DI addition groups every item bought under the same tariff treatment
    (NCM, exporter, incoterm), so more than one `H` block shares the same
    addition number here whenever the shipment repeats an item under it —
    exactly the shape of the Talleres Zitrón DUIMP, one addition (001) for
    all seven items. Blocks are merged back into one addition per number
    below, the same way `_additions` already groups `mercadoria` items under
    one `adicao` when reading the Siscomex XML.
    """
    text = content.decode("latin-1") if isinstance(content, bytes) else content
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    header = {}
    additions = []
    current = None
    tags_seen = set()
    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        parts = raw_line.split("|")
        tag = parts[0].strip()
        if TXT_TAG_PATTERN.match(tag):
            tags_seen.add(tag)
        if tag == "C02":
            header["importer_document"] = _txt_field(parts, 1)
        elif tag == "E" and "exporter" not in header:
            header["exporter"] = _txt_field(parts, 1)
        elif tag == "E05" and "origin_country" not in header:
            header["origin_country"] = _txt_field(parts, 10)
        elif tag == "H":
            current = {
                "customs_value": 0.0,
                "ii_value": 0.0,
                "ipi_rate": 0.0,
                "ipi_value": 0.0,
                "pis_rate": 0.0,
                "pis_value": 0.0,
                "cofins_value": 0.0,
                "icms_value": 0.0,
            }
            additions.append(current)
        elif tag == "I" and current is not None:
            current["product_code"] = _txt_field(parts, 1)
            current["description"] = _txt_field(parts, 4)
            current["ncm"] = _ncm(_txt_field(parts, 5))
            current["uom"] = _txt_field(parts, 7)
            current["quantity"] = _txt_number(
                parts, 8, "I", "quantidade", line_number
            )
            current["net_weight"] = _txt_number(
                parts, 14, "I", "pesoLiquido", line_number
            )
        elif tag == "I18" and current is not None:
            header.setdefault("number", _txt_field(parts, 1))
            header.setdefault("registration_date", _txt_field(parts, 2))
            header.setdefault("clearance_place", _txt_field(parts, 3))
            header.setdefault("clearance_state", _txt_field(parts, 4))
        elif tag == "I25" and current is not None:
            current["addition_number"] = _txt_field(parts, 1)
        elif tag == "N02" and current is not None:
            current["icms_value"] = _txt_number(
                parts, 6, "N02", "vICMS", line_number
            )
        elif tag == "O07" and current is not None:
            current["ipi_value"] = _txt_number(
                parts, 2, "O07", "vIPI", line_number
            )
        elif tag == "O10" and current is not None:
            current["ipi_rate"] = _txt_number(
                parts, 2, "O10", "pIPI", line_number
            )
        elif tag == "P" and current is not None:
            current["customs_value"] = _txt_number(
                parts, 1, "P", "vBC", line_number
            )
            current["ii_value"] = _txt_number(parts, 3, "P", "vII", line_number)
        elif tag == "Q02" and current is not None:
            current["pis_rate"] = _txt_number(
                parts, 3, "Q02", "pPIS", line_number
            )
            current["pis_value"] = _txt_number(
                parts, 4, "Q02", "vPIS", line_number
            )
        elif tag == "S02" and current is not None:
            current["cofins_value"] = _txt_number(
                parts, 4, "S02", "vCOFINS", line_number
            )
        elif tag == "Z":
            afrmm = re.search(r"A\.F\.R\.M\.M\.?\s*[:\-]*\s*R\$\s*([\d.,]+)", raw_line)
            if afrmm:
                header["afrmm"] = _brl_to_float(afrmm.group(1))
            siscomex = re.search(
                r"Taxa Siscomex\s*[:\-]*\s*R\$\s*([\d.,]+)", raw_line
            )
            if siscomex:
                header["customhouse_charges"] = _brl_to_float(siscomex.group(1))

    if not additions:
        raise DeclarationXmlError(
            "No H/addition record found. The expected file is the "
            "despachante's draft-invoice TXT (H/I/I18/N02/O07/O10/P/Q02/S02 "
            "records), not the Siscomex XML."
        )

    exporter = header.get("exporter", "")
    origin_country = header.get("origin_country", "")
    grouped = {}
    order = []
    for addition in additions:
        number = addition.get("addition_number", "") or "1"
        if number not in grouped:
            grouped[number] = []
            order.append(number)
        grouped[number].append(addition)

    prepared_additions = []
    for number in order:
        items = grouped[number]
        customs_value = sum(item["customs_value"] for item in items)
        ii_value = sum(item["ii_value"] for item in items)
        ii_rate = (
            round(ii_value / customs_value * 100, 2) if customs_value else 0.0
        )
        first = items[0]
        prepared_additions.append(
            {
                "number": f"{int(number):03d}" if number.isdigit() else number,
                "ncm": first.get("ncm", ""),
                "customs_value": customs_value,
                "goods_value": customs_value,
                "ii_rate": ii_rate,
                "ii_value": ii_value,
                "ii_regime_code": "",
                "ipi_rate": first["ipi_rate"],
                "ipi_value": sum(item["ipi_value"] for item in items),
                "ipi_regime_code": "",
                "pis_rate": first["pis_rate"],
                "pis_value": sum(item["pis_value"] for item in items),
                "cofins_value": sum(item["cofins_value"] for item in items),
                "pis_cofins_regime_code": "",
                "net_weight": sum(item.get("net_weight", 0.0) for item in items),
                "exporter": exporter,
                "manufacturer": "",
                "origin_country": origin_country,
                "incoterm": "",
                "drawback_act": "",
                "items": [
                    {
                        "sequence": f"{sequence:02d}",
                        "description": (
                            f"{item.get('product_code', '')} - "
                            f"{item.get('description', '')}"
                        ),
                        "quantity": item.get("quantity", 0.0),
                        "unit_value": 0.0,
                        "uom": item.get("uom", ""),
                    }
                    for sequence, item in enumerate(items, start=1)
                ],
            }
        )

    registration_date = _txt_date(header.get("registration_date"))
    return {
        "number": header.get("number", ""),
        "registration_date": registration_date,
        # The despachante's draft never states whether it cleared yet — this
        # file is drawn up the moment the DUIMP registers, not when customs
        # releases the goods. Registration date is the only one there is.
        "clearance_date": registration_date,
        # Not a field the TXT states either. AFRMM only applies to maritime
        # freight, so its presence is the signal this shipment came by sea.
        "transport_via": "1" if header.get("afrmm") else "",
        "clearance_place": header.get("clearance_place", ""),
        "clearance_state": header.get("clearance_state", ""),
        "importer_document": header.get("importer_document", ""),
        "operation_type_code": "",
        "freight": 0.0,
        "insurance": 0.0,
        "icms_value": sum(a["icms_value"] for a in additions),
        "customhouse_charges": header.get("customhouse_charges", 0.0),
        "afrmm": header.get("afrmm", 0.0),
        "gross_weight": 0.0,
        "net_weight": sum(a.get("net_weight", 0.0) for a in additions),
        "additions": prepared_additions,
        "unmapped_tags": sorted(tags_seen - TXT_MAPPED_TAGS),
        "regime_signals": [],
    }
