# Copyright 2018 KMEE INFORMATICA LTDA, Grupo Zenir
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

import base64
import re
import time

from pynfe.utils import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..constants.mdfe import (
    BODY_TYPE,
    EMISSION_TYPE_MDFE_CONTINGENCIA,
    EMISSION_TYPE_MDFE_NORMAL,
    EMISSION_TYPE_MDFE_PROPRIA,
    EMITTER_TYPE,
    FISCAL_MODEL_MDFE,
    MDFE_ENVIRONMENT_PRODUCAO,
    SITUATION_MDFE_ENCERRADA,
    SITUATION_NFE,
    SITUATION_NFE_A_ENVIAR,
    SITUATION_NFE_AUTORIZADA,
    SITUATION_NFE_CANCELADA,
    SITUATION_NFE_EM_DIGITACAO,
    SITUATION_NFE_ENVIADA,
    SITUATION_NFE_REJEITADA,
    STATUS_MDFE,
    TRANSPORT_MODALITY,
    TRANSPORT_MODALITY_RODOVIARIO,
    TRANSPORTER_TYPE,
    WHEELED_TYPE,
)


class SpedDocumento(models.Model):

    _inherit = "l10n_br_fiscal.document"

    emitter_type = fields.Selection(
        selection=EMITTER_TYPE,
        string="Emitter type",
    )
    transporter_type = fields.Selection(
        selection=TRANSPORTER_TYPE, string="Transporter type"
    )
    transport_modality = fields.Selection(
        selection=TRANSPORT_MODALITY,
        string="Modality",
    )
    vehicle_id = fields.Many2one(
        string="Vehicle",
        comodel_name="l10n_br_delivery.carrier.vehicle",
    )
    vehicle_rntrc = fields.Char(
        string="RNTRC",
        related="vehicle_id.rntrc_code",
        store=True,
    )
    license_plate = fields.Char(
        string="License Plate",
        related="vehicle_id.plate",
        store=True,
    )
    vehicle_estate = fields.Many2one(
        comodel_name="res.country.state",
        string="Estate",
        related="vehicle_id.state_id",
        store=True,
    )
    vehicle_ciot = fields.Char(
        string="CIOT Type",
        help="Also known as freight bill",
        related="vehicle_id.ciot",
        store=True,
    )
    wheeled_type_vehicle = fields.Selection(
        selection=WHEELED_TYPE,
        string="Wheeled",
        related="vehicle_id.wheeled_type",
        store=True,
    )
    vehicle_body_type = fields.Selection(
        selection=BODY_TYPE,
        string="Tipo de carroceria",
        related="vehicle_id.body_type",
        store=True,
    )
    vehicle_tare_kg = fields.Float(
        string="Tara (kg)",
        related="vehicle_id.tare_kg",
        store=True,
    )
    vehicle_capacity_kg = fields.Float(
        string="Capacidade (kg)",
        related="vehicle_id.capacity_kg",
        store=True,
    )
    vehicle_capacity_m3 = fields.Float(
        string="Capacidade (m³)",
        related="vehicle_id.capacity_m3",
        store=True,
    )
    shipment_cities_id = fields.Many2many(
        comodel_name="res.city",
        string="Municípios carregamento",
        help="Máximo 50",
    )
    route_estate_ids = fields.Many2many(
        comodel_name="res.country.state",
        string="UFs de percurso",
        help="Máximo 25",
    )
    discharge_estate_id = fields.Many2one(
        comodel_name="res.country.state", string="Estado descarregamento"
    )
    conductor_ids = fields.One2many(
        comodel_name="l10n_br.mdfe.conductor",
        inverse_name="document_id",
    )
    seal_ids = fields.One2many(
        comodel_name="l10n_br.mdfe.seal",
        inverse_name="document_id",
    )
    insurance_ids = fields.One2many(
        comodel_name="l10n_br.mdfe.insurance",
        inverse_name="document_id",
    )
    item_mdfe_ids = fields.One2many(
        comodel_name="l10n_br.mdfe.item",
        inverse_name="mdfe_id",
        inverse="_inverse_item_mdfe_ids",
    )

    referenced_item_ids = fields.One2many(
        comodel_name="l10n_br.mdfe.item",
        inverse_name="document_id",
    )

    situation_mdfe = fields.Selection(
        string="NF-e Situation", selection=SITUATION_NFE, select=True, readonly=True
    )

    @api.depends("item_mdfe_ids.document_id")
    def _inverse_item_mdfe_ids(self):
        for record in self:
            if record.item_mdfe_ids.mapped("document_id"):
                for campo in self._fields.keys():
                    if campo.startswith("vr_"):
                        record[campo] = sum(
                            record.item_mdfe_ids.mapped("document_id").mapped(campo)
                        )

    def _serie_padrao_mdfe(self, empresa, environment_mdfe, emission_type_mdfe):
        serie = False
        if emission_type_mdfe == EMISSION_TYPE_MDFE_NORMAL:
            if environment_mdfe == MDFE_ENVIRONMENT_PRODUCAO:
                serie = empresa.serie_mdfe_production
            else:
                serie = empresa.serie_mdfe_homologation

        elif emission_type_mdfe == EMISSION_TYPE_MDFE_CONTINGENCIA:
            if environment_mdfe == MDFE_ENVIRONMENT_PRODUCAO:
                serie = empresa.serie_mdfe_production_contingency
            else:
                serie = empresa.serie_mdfe_contingency_homologation

        return serie

    @api.onchange("company_id", "document_type", "nfe_environment")
    def _onchange_company_id(self):
        result = super(SpedDocumento, self)._onchange_company_id()

        if self.document_type == FISCAL_MODEL_MDFE:
            result["value"]["nfe_environment"] = self.company_id.nfe_environment
            result["value"]["emission_type_mdfe"] = self.company_id.emission_type_mdfe
            result["value"]["document_serie"] = self._serie_padrao_mdfe(
                self.company_id,
                self.company_id.edoc_purpose,
                self.company_id.emission_type_mdfe,
            )
        return result

    @api.onchange("fiscal_operation_id", "edoc_purpose", "natureza_operacao_id")
    def _onchange_fiscal_operation_id(self):
        result = super(SpedDocumento, self)._onchange_fiscal_operation_id()

        if self.fiscal_operation_id.document_type == FISCAL_MODEL_MDFE:
            result["value"]["emitter_type"] = self.fiscal_operation_id.emitter_type
            result["value"][
                "transporter_type"
            ] = self.fiscal_operation_id.transporter_type
            result["value"][
                "transport_modality"
            ] = self.fiscal_operation_id.transport_modality
            self.situation_mdfe = SITUATION_NFE_EM_DIGITACAO

        return result

    @api.onchange(
        "company_id",
        "document_type",
        "edoc_purpose",
        "nfe_environment",
        "document_serie",
    )
    def _onchange_document_serie(self):
        result = super(SpedDocumento, self)._onchange_document_serie()

        if not self.document_type == FISCAL_MODEL_MDFE:
            return result

        document_serie = self.document_serie and self.document_serie.strip()

        ultimo_numero = self.search(
            [
                ("company_id.cnpj_cpf", "=", self.company_id.cnpj_cpf),
                ("edoc_purpose", "=", self.edoc_purpose),
                ("company_id.nfe_environment", "=", self.company_id.nfe_environment),
                ("document_type", "=", self.document_type),
                ("document_serie", "=", document_serie),
                ("document_number", "!=", False),
            ],
            limit=1,
            order="numero desc",
        )

        result["value"]["document_serie"] = document_serie

        if not ultimo_numero:
            result["value"]["document_number"] = 1
        else:
            result["value"]["document_number"] = ultimo_numero[0].document_number + 1

        return result

    def _confirma_documento(self):
        """
        TODO: Calcular informações do MDF-E:
            - Cidades/Estado do percurso;
            - Realizar validações;
            - Solicitar envio de NF-E em estado a_enviar;
            - Providenciar o envio do MDF-E caso todas as notas estejam
            autorizadas;
            - etc.

        :return:
        """

        result = super(SpedDocumento, self)._confirma_documento()
        for record in self:
            route_estate_ids = record.item_mdfe_ids.mapped("receiver_city_id").mapped(
                "state_id"
            )
            record.route_estate_ids = (
                route_estate_ids - record.company_id.municipio_id.state_id
            )
            auxMT = record.transport_modality
            if auxMT == TRANSPORT_MODALITY_RODOVIARIO and not record.conductor_ids:
                raise UserError(_("Informar no mínimo um condutor!"))

        self.situation_mdfe = SITUATION_NFE_A_ENVIAR

        return result

    def confirma_documento_publico(self):
        self.env["l10n_br_fiscal.documento"].browse(id)

    def envia_documento_publico(self):
        self.env["l10n_br_fiscal.documento"].browse(id)

    def _envia_documento(self):
        self.ensure_one()
        result = super(SpedDocumento, self)._envia_documento()
        if not self.document_type == FISCAL_MODEL_MDFE:
            return result

        mdfe = self.gera_mdfe()
        envio = self.monta_envio()

        if not mdfe.status_servico().resposta.cStat == "107":
            return {}

        consulta = mdfe.consulta(self.key).resposta
        if consulta.cStat in ("100", "101", "132"):
            if consulta.cStat == "100":
                # TODO Corrir o GenetateDS:
                # http://www.davekuhlman.org/generateDS.html#support-for-xs-any
                # implementar gds_build_any para infProt

                self.situation_mdfe = SITUATION_NFE_AUTORIZADA
            elif consulta.cStat == "132":
                self.situation_mdfe = SITUATION_MDFE_ENCERRADA
            return {}

        processo = mdfe.autorizacao(envio).resposta
        xml_str = processo.retorno.request.body
        resposta = processo.resposta
        if resposta.cStat != "103":
            self.xml_error_message = (
                "Código de retorno: "
                + resposta.cStat
                + "\nMensagem: "
                + resposta.xMotivo
            )
            self.situation_mdfe = SITUATION_NFE_REJEITADA
            return {}

        recibo = None
        for i in range(5):
            time.sleep(resposta.infRec.tMed * (1.5 if i else 1.3))
            recibo = mdfe.consulta_recibo(resposta.infRec.nRec).resposta
            if recibo and recibo.cStat == "105":
                continue
            else:
                #
                # Lote recebido, vamos guardar o recibo
                #
                self.recibo = resposta.infRec.nRec
                break

        if recibo.cStat == "105":
            self.situation_mdfe = SITUATION_NFE_ENVIADA

        elif recibo.cStat == "104" and recibo.protMDFe.infProt.cStat == "100":

            # TODO: Gravar o xml
            # TODO: Gravar o pdf
            # TODO: Salvar a hora de autorizaçao

            self.authorization_protocol = recibo.protMDFe.infProt.nProt

            # Autorizada
            if recibo.protMDFe.infProt.cStat == "100":
                self.authorization_protocol = recibo.protMDFe.infProt.nProt
                self.situation_mdfe = SITUATION_NFE_AUTORIZADA

            # xml_str += self._retorno(recibo)
            arquivo = {}
            arquivo["xml"] = xml_str
            arquivo["document_key"] = self.key
            self.grava_xml(arquivo)
        else:
            #
            # Rejeitada por outros motivos, falha no schema etc. etc.
            #
            self.xml_error_message = (
                "Código de retorno: "
                + recibo.protMDFe.infProt.cStat
                + "\nMensagem: "
                + recibo.protMDFe.infProt.xMotivo
            )
            self.situation_mdfe = SITUATION_NFE_REJEITADA

    def gera_pdf(self):
        for record in self:
            if record.document_type not in (FISCAL_MODEL_MDFE):
                return super(SpedDocumento, self).gera_pdf()

            if record.edoc_purpose != EMISSION_TYPE_MDFE_PROPRIA:
                return

        context = self.env.context.copy()
        reportname = "report_sped_documento_mdfe"
        action_py3o_report = self.env.ref(
            "l10n_br_mdfe.action_report_sped_documento_mdfe"
        )

        if not action_py3o_report:
            raise UserError(_("Py3o action report not found for report_name"))

        context["report_name"] = reportname

        py3o_report = (
            self.env["py3o.report"]
            .create({"ir_actions_report_xml_id": action_py3o_report.id})
            .with_context(context)
        )

        res, filetype = py3o_report.create_report(self.ids, {})
        return res

    def encerra_documento(self):

        encerramento = self.monta_encerramento()
        mdfe = self.gera_mdfe()
        processo = mdfe.encerramento(encerramento)
        if processo.resposta.infEvento.cStat == "135":
            self.situation_mdfe = SITUATION_MDFE_ENCERRADA
        mensagem = "Código de retorno: " + processo.resposta.infEvento.cStat
        mensagem += "\nMensagem: " + processo.resposta.infEvento.xMotivo
        self.xml_error_message = mensagem

    def consultar_documento(self):

        mdfe = self.gera_mdfe()
        consulta = mdfe.consulta(self.key)

        if consulta.resposta.cStat in ("100", "101", "132"):
            self.situation_mdfe = STATUS_MDFE[consulta.resposta.cStat]
            self.authorization_protocol = consulta.resposta.protMDFe.anytypeobjs_.nProt
        mensagem = "Código de retorno: " + consulta.resposta.cStat
        mensagem += "\nMensagem: " + consulta.resposta.xMotivo

        self.xml_error_message = mensagem

    def cancelar_documento(self):

        cancelamento = self.monta_cancelamento()
        # Cria objeto para assinar e comunicar
        mdfe = self.gera_mdfe()
        processo = mdfe.cancelamento(cancelamento)
        auxcStat = processo.resposta.infEvento.cStat
        if auxcStat == "101" or auxcStat == "135":
            self.situation_mdfe = SITUATION_NFE_CANCELADA
        mensagem = "Código de retorno: " + processo.resposta.infEvento.cStat
        mensagem += "\nMensagem: " + processo.resposta.infEvento.xMotivo
        self.xml_error_message = mensagem

    def _grava_anexo(
        self,
        nome_arquivo="",
        conteudo="",
        tipo="application/xml",
        model="l10n_br_fiscal.document",
    ):
        self.ensure_one()
        attachment = self.env["ir.attachment"]

        busca = [
            ("res_model", "=", "l10n_br_fiscal.document"),
            ("res_id", "=", self.id),
            ("name", "=", nome_arquivo),
        ]
        attachment_ids = attachment.search(busca)
        attachment_ids.unlink()

        dados = {
            "name": nome_arquivo,
            "datas_fname": nome_arquivo,
            "res_model": "l10n_br_fiscal.document",
            "res_id": self.id,
            "datas": base64.b64encode(conteudo),
            "mimetype": tipo,
        }

        anexo_id = self.env["ir.attachment"].create(dados)

        return anexo_id

    def grava_xml(self, nfe):
        self.ensure_one()
        nome_arquivo = nfe["document_key"] + "-mdfe.xml"
        conteudo = nfe["xml"].encode("utf-8")
        self.arquivo_xml_id = False
        self.arquivo_xml_id = self._grava_anexo(nome_arquivo, conteudo)

        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/{id}/{name}".format(
                id=self.arquivo_xml_id.id, name=self.arquivo_xml_id.name
            ),
            "target": "new",
        }

    def _retorno(self, retorno):

        match = re.search("<soap:Body>(.*?)</soap:Body>", retorno)

        if match:
            resultado = etree.tostring(etree.fromstring(match.group(1))[0])
            resposta = resultado.encode("utf-8")

            return resposta
