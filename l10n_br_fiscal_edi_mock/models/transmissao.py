# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""Transmissao falsa para a erpbrasil.edoc.

Ocupa o lugar da ``TransmissaoSOAP``: recebe a operacao e o XML de envio e
devolve o envelope que a SEFAZ devolveria. Todo o resto (assinatura, montagem
do nfeProc, leitura do protocolo) continua sendo feito pela biblioteca e pelo
modulo da NF-e.
"""
import random
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from lxml import etree

NS = "http://www.portalfiscal.inf.br/nfe"
VER_APLIC = "SEFAZ-SIMULADA"
SUFIXO = " (SEFAZ SIMULADA)"


def agora():
    return datetime.now(timezone(timedelta(hours=-3))).strftime(
        "%Y-%m-%dT%H:%M:%S-03:00"
    )


def protocolo(uf):
    # 15 digitos: 1 (tipo) + UF + ano + sequencial; o 9 no inicio marca o simulador
    return "9%s%s%010d" % (
        uf,
        datetime.now().strftime("%y"),
        random.randint(1, 9999999999),
    )


class RespostaFalsa:
    status_code = 200

    def __init__(self, corpo):
        self.text = (
            '<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">'
            "<soap:Body><nfeResultMsg>%s</nfeResultMsg></soap:Body></soap:Envelope>"
            % corpo
        )
        self.content = self.text.encode()

    def raise_for_status(self):
        return None


class TransmissaoMock:
    """Responde as operacoes da NF-e e da NFC-e (modelos 55 e 65)."""

    def __init__(self, uf, ambiente="2", certificado=None):
        self.uf = uf
        self.ambiente = ambiente
        # a biblioteca assina o XML com o certificado guardado na transmissao
        self.certificado = certificado

    @contextmanager
    def cliente(self, url):
        yield self

    def enviar(self, operacao, xml_etree):
        metodo = getattr(self, "_resp_" + operacao, None)
        if metodo is None:
            raise NotImplementedError(
                "SEFAZ simulada: operacao %s nao tratada" % operacao
            )
        return RespostaFalsa(metodo(xml_etree))

    def _texto(self, raiz, tag):
        achado = raiz.find(".//{%s}%s" % (NS, tag))
        return achado.text if achado is not None else ""

    def _resp_nfeStatusServicoNF(self, raiz):
        return (
            '<retConsStatServ xmlns="%s" versao="4.00"><tpAmb>%s</tpAmb><verAplic>%s</verAplic>'
            "<cStat>107</cStat><xMotivo>Servico em Operacao%s</xMotivo><cUF>%s</cUF>"
            "<dhRecbto>%s</dhRecbto><tMed>1</tMed></retConsStatServ>"
        ) % (NS, self.ambiente, VER_APLIC, SUFIXO, self.uf, agora())

    def _resp_nfeConsultaNF(self, raiz):
        return (
            '<retConsSitNFe xmlns="%s" versao="4.00"><tpAmb>%s</tpAmb><verAplic>%s</verAplic>'
            "<cStat>217</cStat><xMotivo>NF-e nao consta na base de dados da SEFAZ%s</xMotivo>"
            "<cUF>%s</cUF><dhRecbto>%s</dhRecbto><chNFe>%s</chNFe></retConsSitNFe>"
        ) % (
            NS,
            self.ambiente,
            VER_APLIC,
            SUFIXO,
            self.uf,
            agora(),
            self._texto(raiz, "chNFe"),
        )

    def _prot_nfe(self, chave):
        return (
            '<protNFe versao="4.00"><infProt><tpAmb>%s</tpAmb><verAplic>%s</verAplic><chNFe>%s</chNFe>'
            "<dhRecbto>%s</dhRecbto><nProt>%s</nProt><digVal>c2ltdWxhZG8=</digVal><cStat>100</cStat>"
            "<xMotivo>Autorizado o uso da NF-e%s</xMotivo></infProt></protNFe>"
        ) % (self.ambiente, VER_APLIC, chave, agora(), protocolo(self.uf), SUFIXO)

    def _resp_nfeAutorizacaoLote(self, raiz):
        inf = raiz.find(".//{%s}infNFe" % NS)
        chave = (inf.get("Id") or "")[3:] if inf is not None else ""
        return (
            '<retEnviNFe xmlns="%s" versao="4.00"><tpAmb>%s</tpAmb><verAplic>%s</verAplic><cStat>104</cStat>'
            "<xMotivo>Lote processado%s</xMotivo><cUF>%s</cUF><dhRecbto>%s</dhRecbto>%s</retEnviNFe>"
        ) % (
            NS,
            self.ambiente,
            VER_APLIC,
            SUFIXO,
            self.uf,
            agora(),
            self._prot_nfe(chave),
        )

    def _resp_nfeRecepcaoEvento(self, raiz):
        eventos = ""
        for inf in raiz.iter("{%s}infEvento" % NS):
            tipo = self._texto(inf, "tpEvento")
            chave = self._texto(inf, "chNFe")
            # 135: evento registrado e vinculado a NF-e (cancelamento 110111 e carta de correcao 110110)
            eventos += (
                '<retEvento versao="1.00"><infEvento><tpAmb>%s</tpAmb><verAplic>%s</verAplic><cOrgao>%s</cOrgao>'
                "<cStat>135</cStat><xMotivo>Evento registrado e vinculado a NF-e%s</xMotivo><chNFe>%s</chNFe>"
                "<tpEvento>%s</tpEvento><nSeqEvento>%s</nSeqEvento><dhRegEvento>%s</dhRegEvento>"
                "<nProt>%s</nProt></infEvento></retEvento>"
            ) % (
                self.ambiente,
                VER_APLIC,
                self.uf,
                SUFIXO,
                chave,
                tipo,
                self._texto(inf, "nSeqEvento") or "1",
                agora(),
                protocolo(self.uf),
            )
        return (
            '<retEnvEvento xmlns="%s" versao="1.00"><idLote>1</idLote><tpAmb>%s</tpAmb><verAplic>%s</verAplic>'
            "<cOrgao>%s</cOrgao><cStat>128</cStat><xMotivo>Lote de Evento Processado%s</xMotivo>%s</retEnvEvento>"
        ) % (NS, self.ambiente, VER_APLIC, self.uf, SUFIXO, eventos)


def proc_generico(
    xml_enviado, raiz_proc, raiz_prot, ns, chave, uf, motivo, ambiente="2"
):
    """Monta o XML de processo (cteProc, mdfeProc) com um protocolo simulado."""
    numero = protocolo(uf)
    quando = agora()
    proc = etree.Element(
        "{%s}%s" % (ns, raiz_proc), versao="simulada", nsmap={None: ns}
    )
    if xml_enviado:
        try:
            proc.append(
                etree.fromstring(
                    xml_enviado
                    if isinstance(xml_enviado, bytes)
                    else xml_enviado.encode()
                )
            )
        except etree.XMLSyntaxError:
            pass
    prot = etree.SubElement(proc, "{%s}%s" % (ns, raiz_prot), versao="simulada")
    inf = etree.SubElement(prot, "{%s}infProt" % ns)
    for tag, valor in (
        ("tpAmb", ambiente),
        ("verAplic", VER_APLIC),
        ("ch" + raiz_prot[4:], chave),
        ("dhRecbto", quando),
        ("nProt", numero),
        ("cStat", "100"),
        ("xMotivo", motivo + SUFIXO),
    ):
        etree.SubElement(inf, "{%s}%s" % (ns, tag)).text = valor
    return etree.tostring(proc, encoding="unicode"), numero
