# Copyright 2019 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime

from erpbrasil.base import misc
from nfselib.paulistana.v02 import PedidoEnvioLoteRPS as lote_rps_v02
from nfselib.paulistana.v02.PedidoEnvioLoteRPS import (
    CabecalhoType,
    tpCPFCNPJ,
    tpEndereco,
    tpRPS,
)
from nfselib.paulistana.v03 import PedidoEnvioLoteRPS as lote_rps_v03
from unidecode import unidecode

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    EVENT_ENV_HML,
    EVENT_ENV_PROD,
    MODELO_FISCAL_NFSE,
    PROCESSADOR_OCA,
    SITUACAO_EDOC_AUTORIZADA,
    SITUACAO_EDOC_CANCELADA,
    SITUACAO_EDOC_REJEITADA,
)

from ..constants.paulistana import CONSULTA_LOTE, ENVIO_LOTE_RPS

_logger = logging.getLogger(__name__)

# Layout legado (fato gerador até 31/12/2025) = bindings nfselib v02, Versao=1.
# Layout da Reforma Tributária (IBS/CBS) = bindings nfselib v03, Versao=2.
PAULISTANA_BINDINGS = {
    "v02": {"module": lote_rps_v02, "versao": 1},
    "v03": {"module": lote_rps_v03, "versao": 2},
}


def filter_oca_nfse(record):
    if record.processador_edoc == PROCESSADOR_OCA and record.document_type_id.code in [
        MODELO_FISCAL_NFSE,
    ]:
        return True
    return False


def filter_paulistana(record):
    if record.company_id.provedor_nfse == "paulistana":
        return True
    return False


class Document(models.Model):
    _inherit = "l10n_br_fiscal.document"

    nfse_document_key = fields.Char(
        string="NFS-e National Key",
        copy=False,
        index=True,
        help=(
            "Chave de acesso nacional da NFS-e (Reforma Tributária, "
            "ChaveNotaNacional). Tem 50 dígitos, diferente do document_key "
            "(chave de 44 dígitos de NF-e/NFC-e/CT-e, validada por _check_key)."
        ),
    )

    def convert_type_nfselib(self, class_object, object_filed, value):
        if value is None:
            return value

        value_type = ""
        restriction_type = ""
        for field in class_object().member_data_items_:
            if field.name == object_filed:
                value_type = field.child_attrs.get("type", "").replace("xs:", "")
                # data_type é a cadeia de restrição do schema, ex.:
                # ['tpAliquota', 'xs:decimal']; o primeiro item identifica o
                # tipo nomeado, que é quem define fractionDigits.
                data_type = getattr(field, "data_type", None)
                if isinstance(data_type, (list, tuple)) and data_type:
                    restriction_type = data_type[0]
                break

        if value_type in ("int", "long", "byte", "nonNegativeInteger"):
            return int(value)
        elif value_type == "decimal":
            # tpValor tem fractionDigits=2 (valores monetários), mas tpAliquota
            # e tpPercentualCargaTributaria têm fractionDigits=4: arredondar
            # para 2 casas corromperia o valor (ex.: 0.029 -> 0.03).
            decimals = (
                4 if restriction_type in ("tpAliquota", "tpPercentualCargaTributaria") else 2
            )
            return round(float(value), decimals)
        elif value_type == "string":
            return str(value)
        else:
            return value

    def _serialize(self, edocs):
        edocs = super()._serialize(edocs)
        for record in self.filtered(filter_oca_nfse).filtered(filter_paulistana):
            nfse_version = record.company_id.nfse_paulistana_schema or "v02"
            edocs.append(record.serialize_nfse_paulistana(nfse_version=nfse_version))
        return edocs

    def _processador_erpbrasil_nfse(self, **kwargs):
        # Encaminha a versão de schema configurada na empresa para o provedor
        # erpbrasil.edoc, de modo que os envelopes de consulta e cancelamento
        # usem o mesmo layout do RPS (Versao 1 legado / Versao 2 Reforma). O
        # l10n_br_nfse descarta o parâmetro, com aviso no log, enquanto a versão
        # instalada da biblioteca não o aceitar - ver ROADMAP.
        if self.company_id.provedor_nfse == "paulistana":
            kwargs.setdefault(
                "versao_schema", self.company_id.nfse_paulistana_schema or "v02"
            )
        return super()._processador_erpbrasil_nfse(**kwargs)

    def serialize_nfse_paulistana(self, nfse_version="v02"):
        binding = PAULISTANA_BINDINGS[nfse_version]
        dados_lote_rps = self._prepare_lote_rps()
        dados_servico = self._prepare_dados_servico()
        lote_rps = binding["module"].PedidoEnvioLoteRPS(
            Cabecalho=self._serialize_cabecalho(dados_lote_rps, binding),
            RPS=[self._serialize_lote_rps(dados_lote_rps, dados_servico, binding)],
        )
        return lote_rps

    def _serialize_cabecalho(self, dados_lote_rps, binding=None):
        binding = binding or PAULISTANA_BINDINGS["v02"]
        CabecalhoType = binding["module"].CabecalhoType
        tpCPFCNPJ = binding["module"].tpCPFCNPJ
        return CabecalhoType(
            Versao=self.convert_type_nfselib(
                CabecalhoType, "Versao", binding["versao"]
            ),
            CPFCNPJRemetente=tpCPFCNPJ(
                CNPJ=self.convert_type_nfselib(
                    CabecalhoType, "tpCPFCNPJ", dados_lote_rps["cnpj"]
                )
            ),
            transacao=False,  # TODO: Verficar origem do dado
            dtInicio=self.convert_type_nfselib(
                CabecalhoType,
                "dtInicio",
                dados_lote_rps["date_in_out"].split("T", 1)[0],
            ),
            dtFim=self.convert_type_nfselib(
                CabecalhoType, "dtFim", dados_lote_rps["date_in_out"].split("T", 1)[0]
            ),
            QtdRPS=self.convert_type_nfselib(CabecalhoType, "QtdRPS", "1"),
            ValorTotalServicos=self.convert_type_nfselib(
                CabecalhoType, "ValorTotalServicos", dados_lote_rps["total_recebido"]
            ),
            ValorTotalDeducoes=self.convert_type_nfselib(
                CabecalhoType, "ValorTotalDeducoes", dados_lote_rps["carga_tributaria"]
            ),
        )

    def _serialize_lote_rps(self, dados_lote_rps, dados_servico, binding=None):
        binding = binding or PAULISTANA_BINDINGS["v02"]
        tpRPS = binding["module"].tpRPS
        tpChaveRPS = binding["module"].tpChaveRPS
        tpCPFCNPJ = binding["module"].tpCPFCNPJ
        tpEndereco = binding["module"].tpEndereco
        dados_tomador = self._prepare_dados_tomador()
        assinatura = self.assinatura_rps(
            dados_lote_rps, dados_servico, dados_tomador, binding
        )
        if binding["versao"] >= 2:
            # Os dois schemas declaram Assinatura como xs:base64Binary, mas os
            # bindings v02 escrevem o valor cru (esperam str, o base64 é feito
            # pelo erpbrasil.edoc) e os v03 aplicam b64encode no export, que
            # exige bytes.
            assinatura = assinatura.encode("ascii")
        rps = tpRPS(
            Assinatura=assinatura,
            ChaveRPS=tpChaveRPS(
                InscricaoPrestador=self.convert_type_nfselib(
                    tpChaveRPS,
                    "InscricaoPrestador",
                    dados_lote_rps["inscricao_municipal"].zfill(8),
                ),
                SerieRPS=self.convert_type_nfselib(
                    tpChaveRPS, "SerieRPS", dados_lote_rps["serie"]
                ),
                NumeroRPS=self.convert_type_nfselib(
                    tpChaveRPS, "NumeroRPS", dados_lote_rps["numero"]
                ),
            ),
            TipoRPS=self._map_type_rps(dados_lote_rps["tipo"]),
            DataEmissao=self.convert_type_nfselib(
                tpRPS, "DataEmissao", dados_lote_rps["data_emissao"].split("T", 1)[0]
            ),
            StatusRPS=self.convert_type_nfselib(tpRPS, "StatusRPS", "N"),
            TributacaoRPS=self.convert_type_nfselib(
                tpRPS,
                "TributacaoRPS",
                self._map_taxation_rps(dados_lote_rps["natureza_operacao"]),
            ),
            ValorServicos=self.convert_type_nfselib(
                tpRPS, "ValorServicos", dados_servico["valor_servicos"]
            ),
            ValorDeducoes=self.convert_type_nfselib(
                tpRPS, "ValorDeducoes", dados_servico["valor_deducoes"]
            ),
            ValorPIS=self.convert_type_nfselib(
                tpRPS, "ValorPIS", dados_servico["valor_pis_retido"]
            ),
            ValorCOFINS=self.convert_type_nfselib(
                tpRPS, "ValorCOFINS", dados_servico["valor_cofins_retido"]
            ),
            ValorINSS=self.convert_type_nfselib(
                tpRPS, "ValorINSS", dados_servico["valor_inss_retido"]
            ),
            ValorIR=self.convert_type_nfselib(
                tpRPS, "ValorIR", dados_servico["valor_ir_retido"]
            ),
            ValorCSLL=self.convert_type_nfselib(
                tpRPS, "ValorCSLL", dados_servico["valor_csll_retido"]
            ),
            CodigoServico=self.convert_type_nfselib(
                tpRPS, "CodigoServico", dados_servico["codigo_tributacao_municipio"]
            ),
            AliquotaServicos=self.convert_type_nfselib(
                tpRPS, "AliquotaServicos", dados_servico["aliquota"]
            ),
            ISSRetido="true" if dados_servico["iss_retido"] == "1" else "false",
            # FIXME: Hardcoded
            CPFCNPJTomador=self.convert_type_nfselib(
                tpRPS,
                "CPFCNPJTomador",
                tpCPFCNPJ(CNPJ=dados_tomador["cnpj"], CPF=dados_tomador["cpf"]),
            ),
            InscricaoMunicipalTomador=self.convert_type_nfselib(
                tpRPS,
                "InscricaoMunicipalTomador",
                dados_tomador["inscricao_municipal"],
            )
            if dados_tomador["codigo_municipio"]
            == int("%s" % (self.company_id.partner_id.city_id.ibge_code))
            else None,
            InscricaoEstadualTomador=self.convert_type_nfselib(
                tpRPS, "InscricaoEstadualTomador", dados_tomador["inscricao_estadual"]
            ),
            RazaoSocialTomador=self.convert_type_nfselib(
                tpRPS, "RazaoSocialTomador", dados_tomador["razao_social"]
            ),
            EnderecoTomador=tpEndereco(
                Logradouro=self.convert_type_nfselib(
                    tpEndereco, "Logradouro", dados_tomador["endereco"]
                ),
                NumeroEndereco=self.convert_type_nfselib(
                    tpEndereco, "NumeroEndereco", dados_tomador["numero"]
                ),
                ComplementoEndereco=self.convert_type_nfselib(
                    tpEndereco, "ComplementoEndereco", dados_tomador["complemento"]
                ),
                Bairro=self.convert_type_nfselib(
                    tpEndereco, "Bairro", dados_tomador["bairro"]
                ),
                Cidade=self.convert_type_nfselib(
                    tpEndereco, "Cidade", dados_tomador["codigo_municipio"]
                ),
                UF=self.convert_type_nfselib(tpEndereco, "UF", dados_tomador["uf"]),
                CEP=self.convert_type_nfselib(tpEndereco, "CEP", dados_tomador["cep"]),
            ),
            EmailTomador=self.convert_type_nfselib(
                tpRPS, "EmailTomador", dados_tomador["email"]
            ),
            Discriminacao=self.convert_type_nfselib(
                tpRPS,
                "Discriminacao",
                unidecode(
                    dados_servico["discriminacao"]
                    + (
                        "|%s|" % self.fiscal_additional_data.replace("\n", "|")
                        if self.fiscal_additional_data
                        else ""
                    )
                ),
            ),
            ValorCargaTributaria=self.convert_type_nfselib(
                tpRPS,
                "ValorCargaTributaria",
                dados_lote_rps["carga_tributaria_estimada"],
            ),
            PercentualCargaTributaria=self.convert_type_nfselib(
                tpRPS,
                "PercentualCargaTributaria",
                self._percentual_carga_tributaria(dados_lote_rps, dados_servico),
            ),
            FonteCargaTributaria=self.convert_type_nfselib(
                tpRPS, "FonteCargaTributaria", self._fonte_carga_tributaria()
            ),
            MunicipioPrestacao=self.convert_type_nfselib(
                CabecalhoType,
                "Versao",
                self._map_provision_municipality(
                    dados_lote_rps["natureza_operacao"],
                    dados_servico["codigo_municipio"],
                ),
            ),
        )
        if binding["versao"] >= 2:
            self._fill_rps_v03_required(rps, binding, dados_servico)
        return rps

    def _fill_rps_v03_required(self, rps, binding, dados_servico):
        """Popula os campos obrigatórios que só existem no layout da Reforma.

        Nenhum destes elementos existe nos bindings v02 - passá-los ao tpRPS
        legado levantaria TypeError -, por isso são preenchidos depois da
        construção do RPS, apenas quando o schema é o da Reforma.
        """
        valor_servicos = round(float(dados_servico.get("valor_servicos") or 0), 2)
        # Base cobrada: o schema define ValorInicialCobrado XOR
        # ValorFinalCobrado (xs:choice). A SP descontinuou o ValorInicialCobrado
        # (erro 640); a sistemática atual exige o ValorFinalCobrado.
        rps.ValorFinalCobrado = valor_servicos
        rps.ValorIPI = 0.0  # serviço não destaca IPI
        # TODO(MOC): mapear exigibilidade suspensa e pagamento parcelado
        # antecipado conforme o cenário fiscal (0 = não).
        rps.ExigibilidadeSuspensa = 0
        rps.PagamentoParceladoAntecipado = 0
        # NBS deve ter 9 dígitos ([0-9]{9}): usar o código sem máscara.
        codigo_nbs = dados_servico.get("codigo_nbs_unmasked") or dados_servico.get(
            "codigo_nbs"
        )
        rps.NBS = re.sub(r"\D", "", codigo_nbs) if codigo_nbs else None
        # gpPrestacao é xs:choice (cLocPrestacao XOR cPaisPrestacao). Serviço
        # prestado no Brasil -> apenas o município (código IBGE).
        municipio_prestacao = dados_servico.get(
            "municipio_prestacao_servico"
        ) or dados_servico.get("codigo_municipio")
        rps.cLocPrestacao = int(municipio_prestacao) if municipio_prestacao else None
        rps.IBSCBS = self._serialize_ibscbs(binding, dados_servico)

    def _serialize_ibscbs(self, binding, dados_servico):
        """Monta o grupo IBSCBS, obrigatório no RPS do layout da Reforma.

        No envio informa-se a classificação tributária (cClassTrib) e os
        indicadores; os valores monetários de IBS/CBS são calculados e
        devolvidos pelo webservice no retorno.
        """
        module = binding["module"]
        tpIBSCBS = module.tpIBSCBS
        tpValores = module.tpValores
        tpTrib = module.tpTrib
        tpGIBSCBS = module.tpGIBSCBS

        # Os códigos saem da configuração fiscal que já existe, sem pedir nada
        # novo ao usuário: cClassTrib vem do tax_classification_id da linha
        # (computado em _compute_fiscal_tax_ids via map_fiscal_taxes), com
        # fallback no default da empresa; cIndOp vem do operation_indicator_id
        # do produto.
        cclasstrib = dados_servico.get("ibs_cbs_classificacao_tributaria") or (
            self.company_id.tax_classification_id.code or None
        )
        cindop = dados_servico.get("codigo_indicador_operacao") or None
        if not cclasstrib or not cindop:
            # Não bloqueia a emissão, mas registra: sem esses códigos o layout
            # da Reforma rejeita o lote (erro 1001).
            _logger.warning(
                "NFS-e Paulistana %s: IBSCBS incompleto (cClassTrib=%s, "
                "cIndOp=%s). Configure a Classificação Tributária (IBS/CBS) e o "
                "Indicador de Operação para evitar rejeição do lote.",
                self.document_number or self.id,
                cclasstrib,
                cindop,
            )
        try:
            ind_final = int(self.ind_final) if self.ind_final else 0
        except (TypeError, ValueError):
            ind_final = 0

        return tpIBSCBS(
            finNFSe=0,  # 0 = NFS-e regular (único valor aceito pelo schema)
            indFinal=ind_final,
            cIndOp=cindop,
            # 0 = o destinatário é o próprio tomador/adquirente (caso padrão,
            # sem destinatário distinto). 1 exigiria o grupo <dest>.
            indDest=0,
            valores=tpValores(
                trib=tpTrib(
                    gIBSCBS=tpGIBSCBS(cClassTrib=cclasstrib),
                ),
            ),
        )

    def _percentual_carga_tributaria(self, dados_lote_rps, dados_servico):
        """Percentual (fração) da carga tributária estimada IBPT.

        Derivado da razão valor estimado / valor dos serviços para ficar sempre
        coerente com o ValorCargaTributaria enviado (ex.: 183.12 / 8758.72 ->
        0.0209). O tipo tpPercentualCargaTributaria aceita 4 casas decimais.
        """
        valor = float(dados_servico.get("valor_servicos") or 0)
        if not valor:
            return 0.0
        carga = float(dados_lote_rps.get("carga_tributaria_estimada") or 0)
        return carga / valor

    def _fonte_carga_tributaria(self):
        """Fonte/versão da carga tributária estimada (ex.: 'IBPT26.1.L').

        Deriva do campo `version` do último registro IBPT
        (l10n_br_fiscal.tax.estimate) da NBS + empresa - a mesma origem do valor
        estimado -, que traz apenas a versão ('26.1.L'); prefixamos com 'IBPT'
        para formar a fonte esperada pela SP. Fallback para 'IBPT' quando não há
        versão. Limitado a 10 caracteres (tpFonteCargaTributaria).
        """
        fonte = "IBPT"
        nbs = self.fiscal_line_ids[:1].nbs_id
        if nbs:
            estimate = self.env["l10n_br_fiscal.tax.estimate"].search(
                [
                    ("nbs_id", "=", nbs.id),
                    ("company_id", "=", self.company_id.id),
                ],
                order="create_date DESC",
                limit=1,
            )
            if estimate.version:
                fonte = "IBPT" + estimate.version
        return fonte[:10]

    def _serialize_rps(self, dados):
        return tpRPS(
            InscricaoMunicipalTomador=self.convert_type_nfselib(
                tpRPS, "InscricaoMunicipalTomador", dados["inscricao_municipal"]
            ),
            CPFCNPJTomador=tpCPFCNPJ(
                Cnpj=self.convert_type_nfselib(tpCPFCNPJ, "Cnpj", dados["cnpj"]),
                Cpf=self.convert_type_nfselib(tpCPFCNPJ, "Cpf", dados["cpf"]),
            ),
            RazaoSocialTomador=self.convert_type_nfselib(
                tpRPS, "RazaoSocialTomador", dados["razao_social"]
            ),
            EnderecoTomador=tpEndereco(
                Logradouro=self.convert_type_nfselib(
                    tpEndereco, "Logradouro", dados["endereco"]
                ),
                NumeroEndereco=self.convert_type_nfselib(
                    tpEndereco, "NumeroEndereco", dados["numero"]
                ),
                ComplementoEndereco=self.convert_type_nfselib(
                    tpEndereco, "ComplementoEndereco", dados["complemento"]
                ),
                Bairro=self.convert_type_nfselib(tpEndereco, "Bairro", dados["bairro"]),
                Cidade=self.convert_type_nfselib(
                    tpEndereco, "Cidade", dados["codigo_municipio"]
                ),
                UF=self.convert_type_nfselib(tpEndereco, "UF", dados["uf"]),
                CEP=self.convert_type_nfselib(tpEndereco, "CEP", dados["cep"]),
            )
            or None,
        )

    def assinatura_rps(
        self, dados_lote_rps, dados_servico, dados_tomador, binding=None
    ):
        assinatura = ""

        # Inscrição do prestador: o layout legado usa 8 posições, o da Reforma
        # usa 12. A SP reconstrói a mesma string para verificar a assinatura
        # RSA, então largura errada causa o erro 1206.
        versao = binding["versao"] if binding else PAULISTANA_BINDINGS["v02"]["versao"]
        inscr_width = 12 if versao >= 2 else 8
        assinatura += dados_lote_rps["inscricao_municipal"].zfill(inscr_width)
        assinatura += dados_lote_rps["serie"].ljust(5, " ")
        assinatura += dados_lote_rps["numero"].zfill(12)
        assinatura += datetime.strptime(
            dados_lote_rps["data_emissao"], "%Y-%m-%dT%H:%M:%S"
        ).strftime("%Y%m%d")
        assinatura += self._map_taxation_rps(dados_lote_rps["natureza_operacao"])
        assinatura += "N"  # Corrigir - Verificar status do RPS
        assinatura += "S" if dados_servico["iss_retido"] == "1" else "N"
        assinatura += (
            ("%.2f" % dados_servico["valor_servicos"]).replace(".", "").zfill(15)
        )
        assinatura += (
            ("%.2f" % dados_lote_rps["carga_tributaria"]).replace(".", "").zfill(15)
        )
        assinatura += dados_servico["codigo_tributacao_municipio"].zfill(5)
        assinatura += "2" if dados_tomador["cnpj"] else "1"
        assinatura += (dados_tomador["cnpj"] or dados_tomador["cpf"]).zfill(14)
        # assinatura += '3'
        # assinatura += ''.zfill(14)
        # assinatura += 'N'

        return assinatura

    def _map_taxation_rps(self, operation_nature):
        # FIXME: Lidar com diferença de tributado em São Paulo ou não
        dict_taxation = {
            "1": "T",
            "2": "F",
            "3": "A",
            "4": "R",
            "5": "X",
            "6": "X",
        }

        return dict_taxation[operation_nature]

    def _map_provision_municipality(self, operation_nature, municipal_code):
        if operation_nature == "1":
            return None
        else:
            return municipal_code

    def _map_type_rps(self, rps_type):
        dict_type_rps = {
            "1": "RPS",
            "2": "RPS-M",
            "3": "RPS-C",
        }

        return dict_type_rps[rps_type]

    def _eletronic_document_send(self):
        super()._eletronic_document_send()
        for record in self.filtered(filter_oca_nfse).filtered(filter_paulistana):
            processador = record._processador_erpbrasil_nfse()

            protocolo = record.authorization_protocol
            vals = dict()

            if not protocolo:
                for edoc in record.serialize():
                    processo = None
                    for p in processador.processar_documento(edoc):
                        processo = p
                        retorno = ET.fromstring(processo.retorno)

                        if processo.webservice in CONSULTA_LOTE:
                            if processo.resposta.Cabecalho.Sucesso:
                                nfse = retorno.find(".//NFe")
                                # TODO: Verificar resposta do ConsultarLote
                                vals["document_number"] = nfse.find(".//NumeroNFe").text
                                vals["authorization_date"] = nfse.find(
                                    ".//DataEmissaoRPS"
                                ).text
                                vals["verify_code"] = nfse.find(
                                    ".//CodigoVerificacao"
                                ).text
                                record.authorization_event_id.set_done(
                                    status_code=4,
                                    response=vals["status_name"],
                                    protocol_date=vals["authorization_date"],
                                    protocol_number=protocolo,
                                    file_response_xml=processo.retorno,
                                )
                            continue

                        if processo.webservice in ENVIO_LOTE_RPS:
                            # Um Element sem filhos é falsy: com "if retorno"
                            # o tratamento (inclusive o de erro, que monta o
                            # edoc_error_message) era pulado silenciosamente
                            # quando a raiz vinha sem elementos.
                            if retorno is not None:
                                if processo.resposta.Cabecalho.Sucesso:
                                    record._change_state(SITUACAO_EDOC_AUTORIZADA)
                                    vals["status_name"] = _("Procesado com Sucesso")
                                    vals["status_code"] = 4
                                    vals["edoc_error_message"] = ""
                                else:
                                    mensagem_erro = ""
                                    for erro in retorno.findall("Erro"):
                                        codigo = erro.find("Codigo").text
                                        descricao = erro.find("Descricao").text
                                        mensagem_erro += (
                                            codigo + " - " + descricao + "\n"
                                        )

                                    vals["edoc_error_message"] = mensagem_erro
                                    vals["status_name"] = _("Procesado com Erro")
                                    vals["status_code"] = 3
                                    record._change_state(SITUACAO_EDOC_REJEITADA)
                record.write(vals)
        return

    def _document_status(self):
        status = super()._document_status()
        for record in self.filtered(filter_oca_nfse).filtered(filter_paulistana):
            processador = record._processador_erpbrasil_nfse()
            processo = processador.consulta_nfse_rps(
                numero_rps=record.rps_number,
                serie_rps=record.document_serie,
                insc_prest=misc.punctuation_rm(
                    record.company_id.partner_id.l10n_br_im_code or ""
                )
                or None,
                cnpj_prest=misc.punctuation_rm(record.company_id.partner_id.vat),
            )
            consulta = processador.analisa_retorno_consulta(processo)
            if isinstance(consulta, dict):
                retorno_xml = ET.fromstring(processo.retorno)
                # A prefeitura devolve a data em ISO 8601 com "T"
                # (ex.: 2026-07-07T12:07:03); o campo Datetime do Odoo espera
                # "YYYY-MM-DD HH:MM:SS". fromisoformat aceita os dois
                # separadores e devolve um datetime que o Odoo grava direto.
                data_emissao = datetime.fromisoformat(consulta["data_emissao"])
                vals = {
                    "verify_code": consulta["codigo_verificacao"],
                    "document_number": consulta["numero"],
                    "authorization_date": data_emissao,
                }
                # A ChaveNotaNacional (50 dígitos) vem no retorno do layout da
                # Reforma. Não cabe em document_key, que é validado como chave
                # de NF-e (44 dígitos): gravamos no nfse_document_key. No layout
                # legado o elemento não existe, findtext devolve None e o campo
                # fica intocado.
                chave = retorno_xml.findtext(".//ChaveNotaNacional")
                if chave:
                    vals["nfse_document_key"] = chave
                record.write(vals)
                # StatusNFe: "N" = normal/autorizada, "C" = cancelada. Quando
                # a prefeitura já cancelou, o Odoo pode ter ficado autorizado
                # (ex.: um cancelamento anterior sofreu rollback). Reconcilia.
                if retorno_xml.findtext(".//StatusNFe") == "C":
                    status = record._paulistana_sync_cancelada(retorno_xml)
                else:
                    record.authorization_event_id.set_done(
                        status_code=4,
                        response=_("Procesado com Sucesso"),
                        protocol_date=data_emissao,
                        protocol_number=consulta["codigo_verificacao"],
                        file_response_xml=processo.retorno,
                    )
                    # (AUTORIZADA, AUTORIZADA) não existe no WORKFLOW_EDOC:
                    # sem a guarda, consultar uma nota já autorizada levantava
                    # UserError de transição não permitida.
                    if record.state_edoc != SITUACAO_EDOC_AUTORIZADA:
                        record._change_state(SITUACAO_EDOC_AUTORIZADA)
                    status = _("Procesado com Sucesso")
            else:
                # Em caso de erro analisa_retorno_consulta devolve a mensagem
                # (string); no sucesso devolve um dict, que não pode ir para _().
                status = _(consulta)
        return status

    def _paulistana_sync_cancelada(self, retorno_xml):
        """Reflete no Odoo o cancelamento já efetuado na prefeitura.

        Chamado pelo _document_status quando a consulta retorna StatusNFe="C".
        A transição para CANCELADA é feita SEM re-chamar o webservice de
        cancelamento (a nota já está cancelada lá), via a flag de contexto
        lida em _exec_before_SITUACAO_EDOC_CANCELADA. O _document_cancel
        também sincroniza a fatura (cancel_move_ids).
        """
        self.ensure_one()
        if self.state_edoc == SITUACAO_EDOC_CANCELADA:
            return _("Documento já cancelado")
        data_cancelamento = retorno_xml.findtext(".//DataCancelamento")
        justificativa = _("Cancelada na prefeitura (detectado via consulta).")
        if data_cancelamento:
            justificativa = "{} {}".format(
                justificativa,
                _("Data do cancelamento: %s") % data_cancelamento,
            )
        # _document_cancel é o caminho canônico: grava o cancel_reason, faz a
        # transição de estado e, com o l10n_br_account instalado, sincroniza a
        # fatura via cancel_move_ids.
        self.with_context(paulistana_skip_cancel_webservice=True)._document_cancel(
            justificativa
        )
        return _("Documento cancelado na prefeitura")

    def cancel_document_paulistana(self):
        def doc_dict(record):
            return {
                "numero_nfse": record.document_number,
                "codigo_verificacao": record.verify_code,
            }

        status = True
        for record in self.filtered(filter_oca_nfse).filtered(filter_paulistana):
            processador = record._processador_erpbrasil_nfse()
            processo = processador.cancela_documento(doc_numero=doc_dict(record))

            status, message = processador.analisa_retorno_cancelamento_paulistana(
                processo
            )

            if not status:
                raise UserError(_(message))

            record.cancel_event_id = record.event_ids.create_event_save_xml(
                company_id=record.company_id,
                environment=(
                    EVENT_ENV_PROD if record.nfse_environment == "1" else EVENT_ENV_HML
                ),
                event_type="2",
                xml_file=processo.envio_xml,
                document_id=record,
            )

        return status

    def _exec_before_SITUACAO_EDOC_CANCELADA(self, old_state, new_state):
        result = super()._exec_before_SITUACAO_EDOC_CANCELADA(old_state, new_state)
        # O retorno deste hook decide, no _change_state do l10n_br_fiscal_edi,
        # se a transição de estado acontece. Devolver o resultado do super()
        # quando o documento não é da Paulistana evita que a simples instalação
        # deste módulo faça o cancelamento de NF-e/CT-e/MDF-e falhar em
        # silêncio.
        if not self.filtered(filter_oca_nfse).filtered(filter_paulistana):
            return result
        if self.env.context.get("paulistana_skip_cancel_webservice"):
            # A NFS-e já foi cancelada na prefeitura (reconciliação via
            # consulta em _paulistana_sync_cancelada): apenas efetiva a
            # transição no Odoo, sem re-enviar o pedido de cancelamento.
            return True
        return self.cancel_document_paulistana()
