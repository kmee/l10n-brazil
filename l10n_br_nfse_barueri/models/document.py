# Copyright 2019 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from nfselib.barueri.v3_01.servico_enviar_lote_rps_envio import (
    EnviarLoteRpsEnvio,
    ListaRpsType,
    tcCpfCnpj,
    tcDadosServico,
    tcDadosTomador,
    tcEndereco,
    tcIdentificacaoRps,
    tcIdentificacaoTomador,
    tcInfRps,
    tcLoteRps,
    tcRps,
    tcValores,
)

from odoo import _, models
from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    EVENT_ENV_HML,
    EVENT_ENV_PROD,
    MODELO_FISCAL_NFSE,
    PROCESSADOR_OCA,
    SITUACAO_EDOC_AUTORIZADA,
    SITUACAO_EDOC_REJEITADA,
)

from ..constants.barueri import CONSULTAR_SITUACAO_LOTE_RPS, RECEPCIONAR_LOTE_RPS


def filter_oca_nfse(record):
    if record.processador_edoc == PROCESSADOR_OCA and record.document_type_id.code in [
        MODELO_FISCAL_NFSE,
    ]:
        return True
    return False


def filter_barueri(record):
    if record.company_id.provedor_nfse == "barueri":
        return True
    return False


class Document(models.Model):

    _inherit = "l10n_br_fiscal.document"

    def _serialize(self, edocs):
        edocs = super()._serialize(edocs)
        for record in self.filtered(filter_oca_nfse).filtered(filter_barueri):
            edocs.append(record.serialize_nfse_barueri())
        return edocs

    def _serialize_barueri_dados_servico(self):
        self.fiscal_line_ids.ensure_one()
        dados = self._prepare_dados_servico()
        return tcDadosServico(
            Valores=tcValores(
                CodigoServicoPrestado=self.convert_type_nfselib(
                    tcValores, "CodigoServicoPrestado", dados["codigo_servico_prestado"]
                ),
                LocalPrestacaoServico=self.convert_type_nfselib(
                    tcValores, "LocalPrestacaoServico", dados["local_prestacao_servico"]
                ),
                ServicoPrestadoViasPublicas=self.convert_type_nfselib(
                    tcValores,
                    "ServicoPrestadoViasPublicas",
                    dados["servico_prestado_vias_publicas"],
                ),
                EnderecoLogradouroLocalServico=self.convert_type_nfselib(
                    tcValores,
                    "EnderecoLogradouroLocalServico",
                    dados["endereco_logradouro_local_servico"],
                ),
                NumeroLogradouroLocalServico=self.convert_type_nfselib(
                    tcValores,
                    "NumeroLogradouroLocalServico",
                    dados["numero_logradouro_local_servico"],
                ),
                ComplementoLogradouroLocalServico=self.convert_type_nfselib(
                    tcValores,
                    "ComplementoLogradouroLocalServico",
                    dados["complemento_logradouro_local_servico"],
                ),
                BairroLogradouroLocalServico=self.convert_type_nfselib(
                    tcValores,
                    "BairroLogradouroLocalServico",
                    dados["bairro_logradouro_local_servico"],
                ),
                CidadeLogradouroLocalServico=self.convert_type_nfselib(
                    tcValores,
                    "CidadeLogradouroLocalServico",
                    dados["cidade_logradouro_local_servico"],
                ),
                UFLogradouroLocalServico=self.convert_type_nfselib(
                    tcValores,
                    "UFLogradouroLocalServico",
                    dados["UF_logradouro_local_servico"],
                ),
                CEPLogradouroLocalServico=self.convert_type_nfselib(
                    tcValores,
                    "CEPLogradouroLocalServico",
                    dados["CEP_logradouro_local_servico"],
                ),
                QuantidadeServico=self.convert_type_nfselib(
                    tcValores, "QuantidadeServico", dados["quantidade_servico"]
                ),
                ValorServico=self.convert_type_nfselib(
                    tcValores, "ValorServico", dados["valor_servico"]
                ),
                DiscriminacaoServico=self.convert_type_nfselib(
                    tcValores, "DiscriminacaoServico", dados["discriminacao_servico"]
                ),
            ),
            ItemListaServico=self.convert_type_nfselib(
                tcDadosServico, "ItemListaServico", dados["item_lista_servico"]
            ),
            CodigoCnae=self.convert_type_nfselib(
                tcDadosServico, "CodigoCnae", dados["codigo_cnae"]
            ),
        )

    def _serialize_barueri_dados_tomador(self):
        dados = self._prepare_dados_tomador()
        return tcDadosTomador(
            IdentificacaoTomador=tcIdentificacaoTomador(
                IndicadorCPFCNPJTomador=self.convert_type_nfselib(
                    tcDadosTomador,
                    "IndicadorCPFCNPJTomador",
                    dados["indicador_CPF_CNPJ_tomador"],
                ),
                CPFCNPJTomador=tcCpfCnpj(
                    Cnpj=self.convert_type_nfselib(tcCpfCnpj, "Cnpj", dados["cnpj"]),
                    Cpf=self.convert_type_nfselib(tcCpfCnpj, "Cpf", dados["cpf"]),
                ),
            ),
            RazaoSocialNomeTomador=self.convert_type_nfselib(
                tcDadosTomador,
                "RazaoSocialNomeTomador",
                dados["razao_social_nome_tomador"],
            ),
            Endereco=tcEndereco(
                EnderecoLogradouroTomador=self.convert_type_nfselib(
                    tcEndereco,
                    "EnderecoLogradouroTomador",
                    dados["endereco_logradouro_tomador"],
                ),
                NumeroLogradouroTomador=self.convert_type_nfselib(
                    tcEndereco,
                    "NumeroLogradouroTomador",
                    dados["numero_logradouro_tomador"],
                ),
                ComplementoLogradouroTomador=self.convert_type_nfselib(
                    tcEndereco,
                    "ComplementoLogradouroTomador",
                    dados["complemento_logradouro_tomador"],
                ),
                BairroLogradouroTomador=self.convert_type_nfselib(
                    tcEndereco,
                    "BairroLogradouroTomador",
                    dados["bairro_logradouro_tomador"],
                ),
                CidadeLogradouroTomador=self.convert_type_nfselib(
                    tcEndereco,
                    "CidadeLogradouroTomador",
                    dados["cidade_logradouro_tomador"],
                ),
                UFLogradouroTomador=self.convert_type_nfselib(
                    tcEndereco, "UFLogradouroTomador", dados["UF_logradouro_tomador"]
                ),
                CEPLogradouroTomador=self.convert_type_nfselib(
                    tcEndereco, "CEPLogradouroTomador", dados["CEP_logradouro_tomador"]
                ),
                EmailTomador=self.convert_type_nfselib(
                    tcEndereco, "EmailTomador", dados["email_tomador"]
                ),
            )
            or None,
        )

    def _serialize_barueri_rps(self, dados):

        return tcRps(
            InfRps=tcInfRps(
                Id=dados["id"],
                IdentificacaoRps=tcIdentificacaoRps(
                    TipoRPS=self.convert_type_nfselib(
                        tcIdentificacaoRps, "TipoRPS", dados["tipo_RPS"]
                    ),
                    SerieRPS=self.convert_type_nfselib(
                        tcIdentificacaoRps, "SerieRPS", dados["serie_RPS"]
                    ),
                    SerieNFe=self.convert_type_nfselib(
                        tcIdentificacaoRps, "SerieNFe", dados["serie_NFe"]
                    ),
                    NumeroRPS=self.convert_type_nfselib(
                        tcIdentificacaoRps, "NumeroRPS", dados["numero_RPS"]
                    ),
                ),
                DataRPS=self.convert_type_nfselib(
                    tcInfRps, "DataRPS", dados["data_RPS"]
                ),
                HoraRPS=self.convert_type_nfselib(
                    tcInfRps, "HoraRPS", dados["hora_RPS"]
                ),
                SituacaoRPS=self.convert_type_nfselib(
                    tcInfRps, "SituacaoRPS", dados["situacao_RPS"]
                ),
            )
        )

    def _serialize_barueri_lote_rps(self):
        dados = self._prepare_lote_rps()
        return tcLoteRps(
            CPFCNPJTomador=self.convert_type_nfselib(
                tcLoteRps, "CPFCNPJTomador", dados["CPFCNPJ_tomador"]
            ),
            QuantidadeRps=1,
            ListaRps=ListaRpsType(Rps=[self._serialize_barueri_rps(dados)]),
        )

    def serialize_nfse_barueri(self):
        lote_rps = EnviarLoteRpsEnvio(LoteRps=self._serialize_barueri_lote_rps())
        return lote_rps

    def cancel_document_barueri(self):
        for record in self.filtered(filter_oca_nfse).filtered(filter_barueri):
            processador = record._processador_erpbrasil_nfse()
            processo = processador.cancela_documento(
                doc_numero=int(record.document_number)
            )

            status, message = processador.analisa_retorno_cancelamento(processo)

            if not status:
                raise UserError(_(message))

            record.cancel_event_id = record.event_ids.create_event_save_xml(
                company_id=record.company_id,
                environment=(
                    EVENT_ENV_PROD if self.nfe_environment == "1" else EVENT_ENV_HML
                ),
                event_type="2",
                xml_file=processo.envio_xml.decode("utf-8"),
                document_id=record,
            )

            return status

    def _document_status(self):
        for record in self.filtered(filter_oca_nfse):
            processador = record._processador_erpbrasil_nfse()
            processo = processador.consulta_nfse_rps(
                rps_number=int(record.rps_number),
                rps_serie=record.document_serie,
                rps_type=int(record.rps_type),
            )

            return _(
                processador.analisa_retorno_consulta(
                    processo,
                    record.document_number,
                    record.company_cnpj_cpf,
                    record.company_legal_name,
                )
            )

    @staticmethod
    def _get_protocolo(record, processador, vals):
        for edoc in record.serialize():
            processo = None
            for p in processador.processar_documento(edoc):
                processo = p

                if processo.webservice in RECEPCIONAR_LOTE_RPS:
                    if processo.resposta.Protocolo is None:
                        mensagem_completa = ""
                        if processo.resposta.ListaMensagemRetorno:
                            lista_msgs = processo.resposta.ListaMensagemRetorno
                            for mr in lista_msgs.MensagemRetorno:

                                correcao = ""
                                if mr.Correcao:
                                    correcao = mr.Correcao

                                mensagem_completa += (
                                    mr.Codigo
                                    + " - "
                                    + mr.Mensagem
                                    + " - Correção: "
                                    + correcao
                                    + "\n"
                                )
                        vals["edoc_error_message"] = mensagem_completa
                        record._change_state(SITUACAO_EDOC_REJEITADA)
                        record.write(vals)
                        return
                    protocolo = processo.resposta.Protocolo

            if processo.webservice in CONSULTAR_SITUACAO_LOTE_RPS:
                vals["status_code"] = processo.resposta.Situacao

        return vals, protocolo

    @staticmethod
    def _set_response(record, processador, protocolo, vals):
        processo = processador.consultar_lote_rps(protocolo)

        if processo.resposta:
            mensagem_completa = ""
            if processo.resposta.ListaMensagemRetorno:
                lista_msgs = processo.resposta.ListaMensagemRetorno
                for mr in lista_msgs.MensagemRetorno:

                    correcao = ""
                    if mr.Correcao:
                        correcao = mr.Correcao

                    mensagem_completa += (
                        mr.Codigo
                        + " - "
                        + mr.Mensagem
                        + " - Correção: "
                        + correcao
                        + "\n"
                    )
            vals["edoc_error_message"] = mensagem_completa
            if vals.get("status_code") == 3:
                record._change_state(SITUACAO_EDOC_REJEITADA)

        if processo.resposta.ListaNfse:
            xml_file = processo.retorno
            for comp in processo.resposta.ListaNfse.CompNfse:
                vals["document_number"] = comp.Nfse.InfNfse.Numero
                vals["authorization_date"] = comp.Nfse.InfNfse.DataEmissao
                vals["verify_code"] = comp.Nfse.InfNfse.CodigoVerificacao
            record.authorization_event_id.set_done(
                status_code=vals["status_code"],
                response=vals["status_name"],
                protocol_date=vals["authorization_date"],
                protocol_number=protocolo,
                file_response_xml=xml_file,
            )
            record._change_state(SITUACAO_EDOC_AUTORIZADA)

        return vals

    def _eletronic_document_send(self):
        super()._eletronic_document_send()
        for record in self.filtered(filter_oca_nfse).filtered(filter_barueri):
            processador = record._processador_erpbrasil_nfse()

            protocolo = record.authorization_protocol
            vals = dict()

            if not protocolo:
                vals, protocolo = self._get_protocolo(record, processador, vals)

            else:
                vals["status_code"] = 4

            if vals.get("status_code") == 1:
                vals["status_name"] = _("Not received")

            elif vals.get("status_code") == 2:
                vals["status_name"] = _("Batch not yet processed")

            elif vals.get("status_code") == 3:
                vals["status_name"] = _("Processed with Error")

            elif vals.get("status_code") == 4:
                vals["status_name"] = _("Successfully Processed")
                vals["authorization_protocol"] = protocolo

            if vals.get("status_code") in (3, 4):
                vals = self._set_response(record, processador, protocolo, vals)

            record.write(vals)
        return

    def _exec_before_SITUACAO_EDOC_CANCELADA(self, old_state, new_state):
        super()._exec_before_SITUACAO_EDOC_CANCELADA(old_state, new_state)
        return self.cancel_document_barueri()
