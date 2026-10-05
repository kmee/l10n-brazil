# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Representação gráfica da CC-e (evento 110110) no molde do DANFE.

Sem dependência do Odoo: recebe os XMLs (NF-e autorizada, envio e retorno do
evento), o logo e um dicionário de fallback, e devolve o PDF em bytes. Assim o
layout pode ser testado fora da instância.
"""

import re
import unicodedata
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from fpdf import FPDF
from lxml import etree

UF_BY_CODE = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF", "90": "SUFRAMA", "91": "AN",
}  # fmt: skip

EVENT_DESCRIPTION = {"110110": "Carta de Correção"}

HEADER_TEXT = (
    "Representação gráfica do evento 110110 registrado na SEFAZ. Não possui "
    "valor fiscal, simples representação do evento indicado abaixo. Consulte "
    "a autenticidade no portal nacional da NF-e (www.nfe.fazenda.gov.br) ou no "
    "site da SEFAZ autorizadora, pela chave de acesso."
)

DEFAULT_COND_USO = (
    "A Carta de Correção é disciplinada pelo parágrafo 1º-A do art. 7º do "
    "Convênio S/N, de 15 de dezembro de 1970 e pode ser utilizada para "
    "regularização de erro ocorrido na emissão de documento fiscal, desde que o "
    "erro não esteja relacionado com: I - as variáveis que determinam o valor "
    "do imposto tais como: base de cálculo, alíquota, diferença de preço, "
    "quantidade, valor da operação ou da prestação; II - a correção de dados "
    "cadastrais que implique mudança do remetente ou do destinatário; III - a "
    "data de emissão ou de saída."
)


def _plain(text):
    """Sem acento, º vira o, minúsculo e espaços normalizados, para comparar."""
    text = unicodedata.normalize("NFKD", (text or "").replace("º", "o"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


def cond_uso_text(xml_text):
    """Condição de uso para o PDF.

    O leiaute da CC-e obriga o texto fixo, sem acentos, no xCondUso. Quando o
    XML traz exatamente esse texto, o PDF mostra a mesma redação acentuada.
    Qualquer outro texto é mostrado como veio no XML.
    """
    if not xml_text or _plain(xml_text) == _plain(DEFAULT_COND_USO):
        return DEFAULT_COND_USO
    return xml_text


# As fontes internas do PDF são Latin-1: troca o que o usuário costuma colar.
_TRANSLATE = str.maketrans(
    {
        "–": "-", "—": "-", "“": '"', "”": '"', "‘": "'", "’": "'",
        "…": "...", "•": "-", " ": " ",
    }
)  # fmt: skip

LOCAL_TZ = ZoneInfo("America/Sao_Paulo")

MARGIN = 10
WIDTH = 190


def _txt(value):
    if value is None:
        return ""
    value = str(value).translate(_TRANSLATE)
    return value.encode("latin-1", "replace").decode("latin-1")


def _parse(xml):
    if not xml:
        return None
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    parser = etree.XMLParser(remove_blank_text=True, recover=True)
    try:
        return etree.fromstring(xml.strip(), parser=parser)
    except etree.XMLSyntaxError:
        return None


def _find(node, path):
    """Busca por nome local, ignorando namespace: _find(root, "ide/nNF")."""
    if node is None:
        return None
    xpath = ".//" + "/".join(f"*[local-name()='{p}']" for p in path.split("/"))
    found = node.xpath(xpath)
    return found[0] if found else None


def _text(node, path, default=""):
    el = _find(node, path)
    return el.text.strip() if el is not None and el.text else default


def to_local(value):
    """ISO da SEFAZ -> datetime no horário de Brasília.

    Com offset no texto (``-03:00``, ``+00:00``), converte. Sem offset,
    devolve como está.
    """
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo:
        moment = moment.astimezone(LOCAL_TZ)
    return moment


def format_datetime(value):
    moment = to_local(value)
    if moment is None:
        return str(value or "")
    return moment.strftime("%d/%m/%Y %H:%M:%S")


def format_month_year(value):
    moment = to_local(value)
    return moment.strftime("%m/%Y") if moment else ""


def format_cnpj_cpf(value):
    digits = "".join(c for c in (value or "") if c.isdigit())
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return value or ""


def format_cep(value):
    digits = "".join(c for c in (value or "") if c.isdigit())
    return f"{digits[:5]}-{digits[5:]}" if len(digits) == 8 else value or ""


def format_key(key):
    groups = [key[i : i + 4] for i in range(0, len(key), 4)]
    return " ".join(groups[:6]) + "\n" + " ".join(groups[6:])


def _address(node, tag):
    street = ", ".join(
        v.strip(" ,")
        for v in (_text(node, f"{tag}/xLgr"), _text(node, f"{tag}/nro"))
        if v.strip(" ,")
    )
    complement = _text(node, f"{tag}/xCpl")
    return f"{street} - {complement}" if complement else street


def collect_data(nfe_xml, event_request_xml, event_response_xml, fallback=None):
    """Monta o dicionário de campos do layout a partir dos XMLs.

    `fallback` traz o que o Odoo já tem gravado, usado quando o XML não
    tem o campo (XML ausente ou evento antigo).
    """
    # O Odoo devolve False em campo vazio: descarta para cair no default ""
    fb = {k: v for k, v in (fallback or {}).items() if v}
    nfe = _parse(nfe_xml)
    req = _parse(event_request_xml)
    resp = _parse(event_response_xml)

    inf_evento = _find(req, "evento/infEvento")
    det_evento = _find(inf_evento, "detEvento")
    inf_ret = _find(resp, "retEvento/infEvento")
    ide = _find(nfe, "ide")
    emit = _find(nfe, "emit")
    dest = _find(nfe, "dest")
    inf_prot = _find(nfe, "protNFe/infProt")

    key = (
        _text(inf_evento, "chNFe")
        or _text(inf_ret, "chNFe")
        or _text(inf_prot, "chNFe")
        or fb.get("key", "")
    )
    key = "".join(c for c in key if c.isdigit())

    dh_emi = _text(ide, "dhEmi") or fb.get("dh_emi", "")
    dest_id_label, dest_id = "CNPJ / CPF", ""
    if _text(dest, "CNPJ"):
        dest_id = format_cnpj_cpf(_text(dest, "CNPJ"))
    elif _text(dest, "CPF"):
        dest_id = format_cnpj_cpf(_text(dest, "CPF"))
    elif _find(dest, "idEstrangeiro") is not None:
        dest_id_label = "IDENTIFICAÇÃO (ID ESTRANGEIRO)"
        dest_id = _text(dest, "idEstrangeiro")
    else:
        dest_id = format_cnpj_cpf(fb.get("dest_vat", ""))

    tp_evento = _text(inf_evento, "tpEvento") or "110110"
    c_orgao = _text(inf_evento, "cOrgao") or _text(inf_ret, "cOrgao")
    tp_amb = _text(inf_evento, "tpAmb") or _text(inf_ret, "tpAmb") or fb.get("tp_amb")
    c_stat = _text(inf_ret, "cStat") or fb.get("status_code", "")
    x_motivo = _text(inf_ret, "xMotivo") or fb.get("response", "")

    prot_nfe = _text(inf_prot, "nProt") or fb.get("nfe_protocol", "")
    dh_prot_nfe = format_datetime(
        _text(inf_prot, "dhRecbto") or fb.get("nfe_protocol_date", "")
    )

    return {
        "key": key,
        "nfe": {
            "model": _text(ide, "mod") or key[20:22],
            "serie": _text(ide, "serie") or (str(int(key[22:25])) if key else ""),
            "number": _text(ide, "nNF") or (str(int(key[25:34])) if key else ""),
            "month_year": format_month_year(dh_emi),
            "dh_emi": format_datetime(dh_emi),
            "protocol": " - ".join(v for v in (prot_nfe, dh_prot_nfe) if v),
        },
        "emit": {
            "name": _text(emit, "xNome") or fb.get("emit_name", ""),
            "cnpj": format_cnpj_cpf(
                _text(emit, "CNPJ") or _text(emit, "CPF") or fb.get("emit_vat", "")
            ),
            "ie": _text(emit, "IE") or fb.get("emit_ie", ""),
            "address": _address(emit, "enderEmit"),
            "district": _text(emit, "enderEmit/xBairro"),
            "zip": format_cep(_text(emit, "enderEmit/CEP")),
            "city": _text(emit, "enderEmit/xMun"),
            "state": _text(emit, "enderEmit/UF"),
            "phone": _text(emit, "enderEmit/fone"),
        },
        "dest": {
            "name": _text(dest, "xNome") or fb.get("dest_name", ""),
            "id_label": dest_id_label,
            "id": dest_id,
            "country": _text(dest, "enderDest/xPais") or "Brasil",
            "address": _address(dest, "enderDest"),
            "city": _text(dest, "enderDest/xMun"),
            "state": _text(dest, "enderDest/UF"),
        },
        "event": {
            "type": f"{tp_evento} - {EVENT_DESCRIPTION.get(tp_evento, '')}".strip(" -"),
            "sequence": _text(inf_evento, "nSeqEvento") or fb.get("sequence", ""),
            "version": _text(inf_evento, "verEvento")
            or (det_evento.get("versao") if det_evento is not None else "")
            or "1.00",
            "organ": (
                f"{c_orgao} - {UF_BY_CODE[c_orgao]}"
                if c_orgao in UF_BY_CODE
                else c_orgao
            ),
            "environment": {"1": "PRODUÇÃO", "2": "HOMOLOGAÇÃO"}.get(tp_amb, ""),
            "dh_event": format_datetime(_text(inf_evento, "dhEvento"))
            or fb.get("dh_event", ""),
            "status": " - ".join(v for v in (c_stat, x_motivo) if v),
            "protocol": _text(inf_ret, "nProt") or fb.get("protocol_number", ""),
            "dh_reg": format_datetime(
                _text(inf_ret, "dhRegEvento") or fb.get("protocol_date", "")
            ),
        },
        "cond_uso": cond_uso_text(_text(det_evento, "xCondUso")),
        "correction": _text(det_evento, "xCorrecao") or fb.get("justification", ""),
    }


class CCePDF(FPDF):
    def __init__(self):
        super().__init__("P", "mm", "A4")
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self.set_auto_page_break(auto=False)
        self.set_title("CC-e")
        self.set_line_width(0.2)

    # --- primitivas -------------------------------------------------------
    def section(self, y, title):
        self.set_font("Helvetica", "B", 8)
        self.set_xy(MARGIN, y)
        self.cell(WIDTH, 4, _txt(title))
        return y + 4

    def field(self, x, y, w, h, label, value, value_size=10):
        self.rect(x, y, w, h)
        self.set_font("Helvetica", "", 6)
        self.set_xy(x + 1, y + 0.6)
        self.cell(w - 2, 2.6, _txt(label))
        # Reduz a fonte até o valor caber numa linha; abaixo de 6 pt, quebra.
        value = _txt(value)
        size = value_size
        self.set_font("Helvetica", "B", size)
        while size > 6 and self.get_string_width(value) > w - 2 - 2 * self.c_margin:
            size -= 0.5
            self.set_font("Helvetica", "B", size)
        self.set_xy(x + 1, y + 3.4)
        self.multi_cell(w - 2, 4, value, align="L")

    def row(self, y, h, cells, value_size=10):
        x = MARGIN
        for w, label, value in cells:
            self.field(x, y, w, h, label, value, value_size)
            x += w
        return y + h

    def text_box(self, y, text, size, style="", min_h=12):
        self.set_font("Helvetica", style, size)
        self.set_xy(MARGIN + 1.5, y + 1.5)
        self.multi_cell(WIDTH - 3, size * 0.45, _txt(text), align="J")
        h = max(self.get_y() - y + 1.5, min_h)
        self.rect(MARGIN, y, WIDTH, h)
        return y + h

    # --- blocos ------------------------------------------------------------
    def header_block(self, key, logo):
        y, h = MARGIN, 32
        left_w = 125
        self.rect(MARGIN, y, left_w, h)
        self.rect(MARGIN + left_w, y, WIDTH - left_w, h)

        text_x = MARGIN + 2
        if logo:
            text_x = self._draw_logo(logo, MARGIN + 2, y + 2, 26, h - 4) or text_x
        text_w = MARGIN + left_w - text_x - 2

        self.set_xy(text_x, y + 3)
        self.set_font("Helvetica", "B", 11.5)
        self.multi_cell(text_w, 5.5, _txt("CARTA DE CORREÇÃO ELETRÔNICA - CC-e"))
        self.set_xy(text_x, self.get_y() + 2)
        self.set_font("Helvetica", "", 7)
        self.multi_cell(text_w, 3.2, _txt(HEADER_TEXT), align="J")

        right_x = MARGIN + left_w
        self.set_font("Helvetica", "", 7)
        self.set_xy(right_x, y + 5)
        self.cell(WIDTH - left_w, 4, "CHAVE DE ACESSO DA NF-e", align="C")
        self.set_font("Courier", "B", 10)
        self.set_xy(right_x, y + 13)
        self.multi_cell(WIDTH - left_w, 5, format_key(key), align="C")
        return y + h + 3

    def _draw_logo(self, logo, x, y, max_w, max_h):
        """Desenha o logo proporcional; devolve o x onde o texto começa."""
        try:
            from PIL import Image

            logo.seek(0)
            img_w, img_h = Image.open(logo).size
            logo.seek(0)
            ratio = min(max_w / img_w, max_h / img_h)
            w, h = img_w * ratio, img_h * ratio
            self.image(logo, x, y + (max_h - h) / 2, w, h)
            return x + w + 3
        except Exception:  # logo em formato que o fpdf não lê: segue sem
            return None

    def render(self, data, logo=None):
        self.add_page()
        y = self.header_block(data["key"], logo)

        nfe = data["nfe"]
        y = self.section(y, "NOTA FISCAL ELETRÔNICA - NF-e")
        y = self.row(
            y,
            8,
            [
                (14, "MODELO", nfe["model"]),
                (12, "SÉRIE", nfe["serie"]),
                (22, "NÚMERO", nfe["number"]),
                (28, "MÊS/ANO DE EMISSÃO", nfe["month_year"]),
                (40, "DATA/HORA DE EMISSÃO", nfe["dh_emi"]),
                (74, "PROTOCOLO DE AUTORIZAÇÃO", nfe["protocol"]),
            ],
            value_size=9.5,
        )

        emit = data["emit"]
        y = self.section(y + 2, "EMITENTE")
        y = self.row(
            y,
            8,
            [
                (100, "RAZÃO SOCIAL", emit["name"]),
                (45, "CNPJ", emit["cnpj"]),
                (45, "INSCRIÇÃO ESTADUAL", emit["ie"]),
            ],
        )
        y = self.row(
            y,
            8,
            [
                (100, "ENDEREÇO", emit["address"]),
                (45, "BAIRRO/DISTRITO", emit["district"]),
                (45, "CEP", emit["zip"]),
            ],
        )
        y = self.row(
            y,
            8,
            [
                (100, "MUNICÍPIO", emit["city"]),
                (45, "UF", emit["state"]),
                (45, "TELEFONE", emit["phone"]),
            ],
        )

        dest = data["dest"]
        y = self.section(y + 2, "DESTINATÁRIO / REMETENTE")
        y = self.row(
            y,
            8,
            [
                (100, "NOME / RAZÃO SOCIAL", dest["name"]),
                (45, dest["id_label"], dest["id"]),
                (45, "PAÍS", dest["country"]),
            ],
        )
        y = self.row(
            y,
            8,
            [
                (100, "ENDEREÇO", dest["address"]),
                (45, "MUNICÍPIO", dest["city"]),
                (45, "UF", dest["state"]),
            ],
        )

        event = data["event"]
        y = self.section(y + 2, "EVENTO")
        y = self.row(
            y,
            8,
            [
                (100, "TIPO DE EVENTO", event["type"]),
                (45, "SEQUÊNCIA DO EVENTO", event["sequence"]),
                (45, "VERSÃO DO EVENTO", event["version"]),
            ],
        )
        y = self.row(
            y,
            8,
            [
                (100, "ÓRGÃO", event["organ"]),
                (45, "AMBIENTE", event["environment"]),
                (45, "DATA/HORA DO EVENTO", event["dh_event"]),
            ],
        )
        y = self.row(
            y,
            8,
            [
                (100, "STATUS", event["status"]),
                (45, "PROTOCOLO DE REGISTRO", event["protocol"]),
                (45, "DATA/HORA DO REGISTRO", event["dh_reg"]),
            ],
        )

        y = self.section(y + 2, "CONDIÇÃO DE USO")
        y = self.text_box(y, data["cond_uso"], 7, min_h=20)

        y = self.section(y + 2, "CORREÇÃO")
        self.text_box(y, data["correction"], 10, style="B", min_h=20)


def render_cce_pdf(pages):
    """`pages`: lista de (data, logo_bytes_ou_None). Uma página por CC-e."""
    pdf = CCePDF()
    for data, logo in pages:
        pdf.render(data, BytesIO(logo) if logo else None)
    return bytes(pdf.output())
