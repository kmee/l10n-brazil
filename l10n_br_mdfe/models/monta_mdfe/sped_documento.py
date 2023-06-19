# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from __future__ import unicode_literals

import logging
import tempfile

from dateutil.relativedelta import relativedelta
from erpbrasil.base import misc
from mdfelib.v3_00 import (
    evCancMDFe,
    evEncMDFe,
    mdfe as mdfe3,
    mdfeModalRodoviario as rodo3,
    procMDFe,
)
from pynfe.processamento.comunicacao import ComunicacaoMDFe

from odoo import fields, models

_logger = logging.getLogger(__name__)

try:
    from pybrasil.data import data_hora_horario_brasilia, parse_datetime
except (ImportError, IOError) as err:
    _logger.debug(err)

_logger = logging.getLogger(__name__)


class SpedDocumento(models.Model):
    _inherit = "l10n_br_fiscal.document"

    def _prepare_ender_emtit(self):
        ende_emi = mdfe3.TEndeEmi()

        ende_emi.set_xLgr(self.company_id.endereco)
        ende_emi.set_nro(self.company_id.document_number)
        ende_emi.set_xBairro(self.company_id.bairro)
        ende_emi.set_cMun(self.company_id.municipio_id.codigo_ibge[:7])
        ende_emi.set_xMun(self.company_id.municipio_id.name)
        ende_emi.set_CEP(misc.punctuation_rm(self.company_id.cep))
        ende_emi.set_UF(self.company_id.estado)

        return ende_emi

    def _prepare_emit(self):
        emit_type = mdfe3.emitType()
        emit_type.set_CNPJ(self.company_id.cnpj_cpf_numero)
        emit_type.set_IE(misc.punctuation_rm(self.company_id.participante_id.ie))
        emit_type.set_xNome(self.company_id.participante_id.razao_social)
        emit_type.set_xFant(self.company_id.participante_id.fantasia)
        emit_type.set_enderEmit(self._prepare_ender_emtit())

        return emit_type

    def _prepare_ide(self):

        ide_type = mdfe3.ideType()

        ide_type.set_cUF(self.company_id.municipio_id.state_id.codigo_ibge)
        ide_type.set_UFIni(self.company_id.estado)
        ide_type.set_UFFim(self.discharge_estate_id.uf or self.company_id.estado)

        ide_type.set_tpAmb(self.environment_mdfe)
        ide_type.set_tpEmit(self.emitter_type)
        ide_type.set_mod(self.document_type)
        ide_type.set_serie(self.serie)
        ide_type.set_nMDF(str(int(self.numero)))
        ide_type.set_modal(self.fiscal_operation_id.transport_modality)

        ide_type.set_procEmi("0")
        ide_type.set_verProc("Odoo")

        dhIniViagem = data_hora_horario_brasilia(
            parse_datetime(self.date_in_out + " GMT")
        ).strftime("%Y-%m-%dT%H:%M:%S-03:00")
        ide_type.set_dhIniViagem(dhIniViagem)
        ide_type.validate_TDateTimeUTC(ide_type.dhIniViagem)
        ide_type.set_dhEmi(
            data_hora_horario_brasilia(
                parse_datetime(self.document_date + " GMT")
            ).strftime("%Y-%m-%dT%H:%M:%S-03:00")
        )

        ide_type.set_infMunCarrega(
            [
                mdfe3.infMunCarregaType(
                    cMunCarrega=municipio.codigo_ibge[:7], xMunCarrega=municipio.name
                )
                for municipio in self.shipment_cities_id
            ]
        )

        ide_type.set_infPercurso(
            [
                mdfe3.infPercursoType(UFPer=percurso.uf)
                for percurso in self.route_estate_ids
            ]
        )

        ide_type.set_indCanalVerde(None)
        ide_type.set_tpEmis("1")
        ide_type.set_tpTransp(self.transporter_type or None)

        return ide_type

    def _prepare_tot(self):
        tot_type = mdfe3.totType()

        tot_type.set_qCTe(None)  # todo: quantity de CTe's de lista_cte
        tot_type.set_qNFe("1")  # todo: quantity de NFe's de lista_nfe
        tot_type.set_qMDFe(None)
        tot_type.set_vCarga("3044.00")  # todo: soma do valor das NFe's,
        # @mileo essses valores eles não tem nas linhas
        tot_type.set_cUnid("01")  # 01-KG, 02-TON
        tot_type.set_qCarga("57.0000")  # todo: Peso Bruto Total

        return tot_type

    def _prepare_modal(self):
        vehicle = rodo3.veicTracaoType()

        rodo = rodo3.rodo()

        vehicle.set_cInt("0001")
        vehicle.set_plate(misc.punctuation_rm(self.license_plate))
        vehicle.set_RENAVAM(None)
        vehicle.set_tara(str(int(self.vehicle_tare_kg)) or "0")
        vehicle.set_capKG(str(int(self.vehicle_capacity_kg)) or "0")
        vehicle.set_capM3(str(int(self.vehicle_capacity_m3)) or "0")
        vehicle.set_prop(None)
        vehicle.set_condutor(self.conductor_ids.monta_mdfe())
        vehicle.set_tpRod(self.wheeled_type_vehicle or "")
        vehicle.set_tpCar(str(int(self.vehicle_body_type)).zfill(2) or "00")
        vehicle.set_UF(self.vehicle_estate.uf or "")

        rodo.set_infANTT(None)
        rodo.set_veicTracao(vehicle)
        # rodo.set_veicReboque(None)
        rodo.set_codAgPorto(None)
        # rodo.set_lacRodo(None)

        return mdfe3.infModalType(versaoModal="3.00", anytypeobjs_=rodo)

    def _prepare_inf_doc(self):

        inf_mun_descarga = self.item_mdfe_ids.monta_mdfe()
        return mdfe3.infDocType(infMunDescarga=inf_mun_descarga)

    def module_11(self, value):
        result_sum = 0
        m = 2
        for i in range(len(value) - 1, -1, -1):
            c = value[i]
            result_sum += int(c) * m
            m += 1
            if m > 9:
                m = 2

        digit = 11 - (result_sum % 11)
        if digit > 9:
            digit = 0

        return digit

    def generate_key(self, inf_mdfe):
        number = "nMDF"
        numerical_code = "cMDF"

        key = unicode_literals(inf_mdfe.ide.cUF).zfill(2)
        key += unicode_literals(inf_mdfe.ide.dhEmi[2:7].replace("-", ""))
        key += unicode_literals(inf_mdfe.emit.CNPJ).zfill(14)
        key += unicode_literals(inf_mdfe.ide.mod).zfill(2)
        key += unicode_literals(inf_mdfe.ide.serie).zfill(3)
        key += unicode_literals(getattr(inf_mdfe.ide, number)).zfill(9)
        key += unicode_literals(inf_mdfe.ide.tpEmis).zfill(1)
        result_sum = 0
        for c in key:
            result_sum += int(c) ** 3**2

        code = unicode_literals(result_sum)
        if len(code) > 8:
            code = code[-8:]
        else:
            code = code.rjust(8, "0")

        key += code
        setattr(inf_mdfe.ide, numerical_code, code)
        digit = self.module_11(key)
        inf_mdfe.ide.set_cDV(str(digit))
        key += unicode_literals(digit)

        return key

    def monta_envio(self):
        self.ensure_one()

        inf_mdfe = procMDFe.infMDFeType()
        inf_mdfe.set_versao("3.00")
        inf_mdfe.set_ide(self._prepare_ide())
        inf_mdfe.set_emit(self._prepare_emit())
        inf_mdfe.set_infModal(self._prepare_modal())
        inf_mdfe.set_infDoc(self._prepare_inf_doc())
        inf_mdfe.set_seg(self.insurance_ids.monta_mdfe())
        inf_mdfe.set_tot(self._prepare_tot())
        inf_mdfe.set_lacres(self.seal_ids.monta_mdfe())

        inf_mdfe.set_infAdic(None)  # Usar a função do divino
        self.document_key = self.generate_key(inf_mdfe)
        inf_mdfe.set_Id("MDFe" + self.document_key)
        # autXML=None,

        inf_mdfe.original_tagname_ = "infMDFe"

        shipping = procMDFe.TMDFe(infMDFe=inf_mdfe)
        shipping.original_tagname_ = "MDFe"
        return shipping

    def gera_mdfe(self):

        cert = self.company_id.certificado_id.arquivo.decode("base64")
        pw = self.company_id.certificado_id.senha
        uf = self.company_id.estado

        caminho = tempfile.gettempdir() + "/certificado.pfx"
        f = open(caminho, "wb")
        f.write(cert)
        f.close()

        return ComunicacaoMDFe(
            certificado=caminho,
            senha=pw,
            uf=uf,
            homologacao=(self.environment_mdfe == "2"),
        )

    def monta_encerramento(self):

        nSeqEvento = "01"
        tpEvento = "110112"

        closure = evEncMDFe.evEncMDFe()
        closure.set_descEvento("Encerramento")
        closure.set_nProt(self.authorization_protocol)
        closure.set_dtEnc(fields.Date.today())
        closure.set_cUF(self.company_id.municipio_id.state_id.codigo_ibge)
        closure.set_cMun(self.company_id.municipio_id.codigo_ibge[:7])

        det_evento = evEncMDFe.detEventoType(versaoEvento="3.00", anytypeobjs_=closure)

        inf_evento = evEncMDFe.infEventoType()
        inf_evento.set_cOrgao(self.company_id.municipio_id.state_id.codigo_ibge)
        inf_evento.set_tpAmb("2")
        inf_evento.set_CNPJ("41426966004836")
        inf_evento.set_chMDFe(self.document_key)
        inf_evento.set_dhEvento(
            (
                fields.Datetime.from_string(fields.Datetime.now())
                + relativedelta(hours=-3)
            ).strftime("%Y-%m-%dT%H:%M:%S-03:00")
        )
        inf_evento.set_tpEvento(tpEvento)
        inf_evento.set_nSeqEvento(nSeqEvento)
        inf_evento.set_detEvento(det_evento)
        inf_evento.set_Id("ID" + tpEvento + self.document_key + nSeqEvento)

        return inf_evento

    def monta_cancelamento(self):

        nSeqEvento = "01"
        tpEvento = "110111"

        cancelamento = evCancMDFe.evCancMDFe()
        cancelamento.set_descEvento("Cancelamento")
        cancelamento.set_nProt(self.authorization_protocol)
        cancelamento.set_xJust(self.justificativa)

        det_evento = evEncMDFe.detEventoType(
            versaoEvento="3.00", anytypeobjs_=cancelamento
        )

        inf_evento = evEncMDFe.infEventoType()
        inf_evento.set_cOrgao(self.company_id.municipio_id.state_id.codigo_ibge)
        inf_evento.set_tpAmb("2")
        inf_evento.set_CNPJ("41426966004836")
        inf_evento.set_chMDFe(self.document_key)
        inf_evento.set_dhEvento(
            (
                fields.Datetime.from_string(fields.Datetime.now())
                + relativedelta(hours=-3)
            ).strftime("%Y-%m-%dT%H:%M:%S-03:00")
        )
        inf_evento.set_tpEvento(tpEvento)
        inf_evento.set_nSeqEvento(nSeqEvento)
        inf_evento.set_detEvento(det_evento)
        inf_evento.set_Id("ID" + tpEvento + self.document_key + nSeqEvento)

        return inf_evento
