# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

PROVEDOR_NFSE_NACIONAL = "nacional"

DANFSE_NACIONAL_TEMPLATE = "main_template_danfse_nacional"

ADN_BASE_URL = {
    "1": "https://sefin.nfse.gov.br/SefinNacional",
    "2": "https://sefin.producaorestrita.nfse.gov.br/SefinNacional",
}

PRESTADOR_SELF_EMITTED_EXCLUDED = (
    "nfse10_IM",
    "nfse10_xNome",
    "nfse10_end",
    "nfse10_fone",
    "nfse10_email",
)

NFSE_NACIONAL_CANCEL_EVENT = "101101"
NFSE_NACIONAL_CANCEL_OFICIO_EVENT = "305101"
NFSE_NACIONAL_CANCEL_MOTIVES = [
    ("1", "Erro na emissão"),
    ("2", "Serviço não prestado"),
    ("9", "Outros"),
]

IBSCBS_CST_DEFAULT = "000"
IBSCBS_CLASS_TRIB_DEFAULT = "000001"
IBSCBS_FIN_NFSE_NORMAL = "0"
IBSCBS_IND_DEST_TOMADOR = "0"

# Withholding type for PIS/COFINS (TSTipoRetPISCofins, tiposComplexos_v1.01.xsd).
# The schema table lists ten codes, but 1 and 2 say nothing about the CSLL, while
# 0 and 3 to 9 already name all eight combinations of PIS, COFINS and CSLL held.
TP_RET_PIS_COFINS = {
    (False, False, False): "0",
    (True, True, True): "3",
    (True, True, False): "4",
    (True, False, False): "5",
    (False, True, False): "6",
    (False, True, True): "7",
    (False, False, True): "8",
    (True, False, True): "9",
}

NFSE_NACIONAL_LAYOUT_VERSION = "1.01"
