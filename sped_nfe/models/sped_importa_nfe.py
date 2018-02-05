# -*- coding: utf-8 -*-
#
# Copyright 2017 KMEE INFORMATICA LTDA
#   Hugo Borges <hugo.borges@kmee.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from odoo import _, models, fields, api

import base64
import re
import gzip
import io
import fnmatch
import os
import codecs
import glob
from lxml import objectify, etree
from odoo.exceptions import UserError
import logging
import threading
from pybrasil.data import UTC
import dateutil.parser

from odoo.addons.l10n_br_base.constante_tributaria import (
    SITUACAO_FISCAL_CANCELADO,
    SITUACAO_NFE_CANCELADA,
)

_logger = logging.getLogger(__name__)


class ImportaNFe(models.Model):

    _name = 'sped.importa.nfe'
    _description = 'Importa NFe'

    chave = fields.Char(
        string='Chave',
        size=44,
        # required=True,
    )
    quantidade_diretorio = fields.Integer(
        string='Quantidade Diretório',
    )
    quantidade_importada = fields.Integer(
        string='Quantidade Importada',
    )
    empresa_id = fields.Many2one(
        comodel_name='sped.empresa',
        string='Empresa',
        # required=True,
    )

    purchase_id = fields.Many2one(
        comodel_name='purchase.order',
    )

    caminho = fields.Char(
        string='Caminho',
    )

    def importa_nfe_cancelada(self, xml):

        nfe = objectify.fromstring(xml)
        chave = str(nfe.evento.infEvento.chNFe)
        documentos = self.env['sped.documento'].search([
            ('chave', '=', chave),
        ])

        if not documentos:
            raise UserError(
                _("Nenhum documento encontrado para o "
                  "protocolo de cancelamento fornecido")
            )

        for documento in documentos:
            _logger.info(u'Importando NF-e cancelada')

            nome_arquivo = chave + '-01-proc-can.xml'
            conteudo = xml.encode('utf-8')
            if not documento.arquivo_xml_autorizacao_cancelamento_id:
                documento.arquivo_xml_autorizacao_cancelamento_id = \
                    documento._grava_anexo(nome_arquivo, conteudo)


            documento.justificativa = nfe.evento.infEvento.detEvento.xJust
            documento.protocolo_cancelamento = nfe.retEvento.infEvento.nProt

            data_cancelamento = dateutil.parser.parse(
                nfe.retEvento.infEvento.dhRegEvento.text)
            data_cancelamento = UTC.normalize(data_cancelamento)

            documento.data_hora_cancelamento = data_cancelamento

            documento.situacao_fiscal = SITUACAO_FISCAL_CANCELADO
            documento.situacao_nfe = SITUACAO_NFE_CANCELADA

        return documentos

    @api.multi
    def importa_caminho(self, autocommit=True):

        if not self.caminho:
            return

        def find_files(directory, pattern):
            for root, dirs, files in os.walk(directory):
                for basename in files:
                    if fnmatch.fnmatch(basename, pattern.lower()):
                        filename = os.path.join(root, basename)
                        yield filename
                    if fnmatch.fnmatch(basename, pattern.upper()):
                        filename = os.path.join(root, basename)
                        yield filename

        self.quantidade_diretorio = 0
        self.quantidade_importada = 0
        notas_canceladas = []

        for filename in find_files(self.caminho, '*.xml'):
            try:
                if 'proc-can' in filename:
                    notas_canceladas.append(filename)
                    continue

                self.quantidade_diretorio += 1
                tree = etree.parse(filename)
                xml = etree.tostring(tree.getroot())
                nfe = objectify.fromstring(xml)
                documento = self.env['sped.documento'].new()
                documento.importado_xml = True
                documento.modelo = nfe.NFe.infNFe.ide.mod.text
                resultado = documento.le_nfe(xml=xml)
                if resultado:
                    print u"Importado:  " + filename
                    self.quantidade_importada += 1
                else:
                    print u"Não importado:  " + filename
                if autocommit:
                    self.env.cr.commit()
            except Exception as e:
                print u"Exception:  " + filename

        for filename in notas_canceladas:
            try:
                tree = etree.parse(filename)
                xml = etree.tostring(tree.getroot())
                nfe = objectify.fromstring(xml)

                if (nfe.evento.infEvento.detEvento.
                        descEvento == 'Cancelamento'):
                    self.importa_nfe_cancelada(xml)

            except Exception as e:
                print u"Exception:  " + filename

    # def _importar_caminho(self, diretorio):
    #
    #     _logger.info(u'Importando diretório' + diretorio)
    #     def find_files_in_folder(directory, pattern):
    #         os.chdir(directory)
    #         for file in glob.glob(pattern.lower()):
    #             yield file
    #         for file in glob.glob(pattern.upper()):
    #             yield file
    #
    #     self.quantidade_diretorio += 1
    #     self.quantidade_diretorio =
    #     for filename in find_files_in_folder(diretorio, '*.xml'):
    #         self.quantidade_diretorio += 1
    #         with api.Environment.manage():
    #             new_cr = self.pool.cursor()
    #             self = self.with_env(self.env(cr=new_cr))
    #
    #             try:
    #                 tree = etree.parse(filename)
    #                 xml = etree.tostring(tree.getroot())
    #                 nfe = objectify.fromstring(xml)
    #                 documento = self.env['sped.documento'].new()
    #                 documento.importado_xml = True
    #                 documento.modelo = nfe.NFe.infNFe.ide.mod.text
    #                 resultado = documento.le_nfe(xml=xml)
    #                 if resultado:
    #                     mensagem = u"Importado:  " + filename
    #                     self.quantidade_importada += 1
    #                 else:
    #                     mensagem = u"Não importado:  " + filename
    #                 _logger.info(mensagem)
    #                 self._cr.commit()
    #             except Exception:
    #                 _logger.info(u'Exception: ao importar o xml')
    #                 self._cr.rollback()
    #             finally:
    #                 self._cr.close()
    #
    #         # try:
    #         #     tree = etree.parse(filename)
    #         #     xml = etree.tostring(tree.getroot())
    #         #     nfe = objectify.fromstring(xml)
    #         #     documento = self.env['sped.documento'].new()
    #         #     documento.importado_xml = True
    #         #     documento.modelo = nfe.NFe.infNFe.ide.mod.text
    #         #     resultado = documento.le_nfe(xml=xml)
    #         #     if resultado:
    #         #         print u"Importado:  " + filename
    #         #     else:
    #         #         print u"Não importado:  " + filename
    #         #
    #         #     self.env.cr.commit()
    #         # except Exception as e:
    #         #     print u"Exception:  " + filename
    #
    # @api.multi
    # def importa_caminho(self, autocommit=True):
    #
    #     if not self.caminho:
    #         return
    #
    #     lista_de_diretorios = [x[0] for x in os.walk(self.caminho)]
    #
    #     # chunks = [lista_de_diretorios[x:x + 10] for x in xrange(0, len(lista_de_diretorios), 10)]
    #
    #     for diretorio in lista_de_diretorios:
    #         _logger.info(u'Criando novo thread de importação no diretório' + diretorio)
    #         threaded_calculation = threading.Thread(target=self._importar_caminho(diretorio), args=())
    #         threaded_calculation.start()
    #     return True
    #
    #     # if not self.caminho:
    #     #     return
    #     #
    #     # def find_files(directory, pattern):
    #     #     for root, dirs, files in os.walk(directory):
    #     #         for basename in files:
    #     #             if fnmatch.fnmatch(basename, pattern.lower()):
    #     #                 filename = os.path.join(root, basename)
    #     #                 yield filename
    #     #             if fnmatch.fnmatch(basename, pattern.upper()):
    #     #                 filename = os.path.join(root, basename)
    #     #                 yield filename
    #     #
    #     # for filename in find_files(self.caminho, '*.xml'):

    @api.multi
    def importa_nfe(self, chave=None, empresa=None):
        self.ensure_one()
        empresa = self.empresa_id or empresa
        chave = self.chave or chave

        nfe_result = self.download_nfe(empresa, chave)

        if nfe_result['code'] == '138':

            nfe = objectify.fromstring(nfe_result['nfe'])
            documento = self.env['sped.documento'].new()
            documento.modelo = nfe.NFe.infNFe.ide.mod.text
            documento.le_nfe(xml=nfe_result['nfe'])
        else:
            raise models.ValidationError(_(
                nfe_result['code'] + ' - ' + nfe_result['message'])
            )
        if self.purchase_id:
            documento.purchase_order_ids = [(4, self.purchase_id.id)]
        return {
            'name': _("Importar NFe"),
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'sped.documento',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': documento.id,
            'context': {'active_id': documento.id},
            'flags': {'form': {'action_buttons': True, 'options': {'mode': 'edit'}}},
        }

    def download_nfe(self, empresa, chave):
        p = empresa.processador_nfe()
        cnpj_partner = re.sub('[^0-9]', '', empresa.cnpj_cpf)

        result = p.consultar_distribuicao(
            cnpj_cpf=cnpj_partner,
            chave_nfe=chave)

        if result.resposta.status == 200:  # Webservice ok
            if result.resposta.cStat.valor == '138':
                nfe_zip = \
                    result.resposta.loteDistDFeInt.docZip[0].docZip.valor
                orig_file_desc = gzip.GzipFile(
                    mode='r',
                    fileobj=io.StringIO(
                        base64.b64decode(nfe_zip))
                )
                nfe = orig_file_desc.read()
                orig_file_desc.close()

                return {
                    'code': result.resposta.cStat.valor,
                    'message': result.resposta.xMotivo.valor,
                    'file_sent': result.envio.xml,
                    'file_returned': result.resposta.xml,
                    'nfe': nfe,
                }
            else:
                return {
                    'code': result.resposta.cStat.valor,
                    'message': result.resposta.xMotivo.valor,
                    'file_sent': result.envio.xml,
                    'file_returned': result.resposta.xml
                }
        else:
            return {
                'code': result.resposta.status,
                'message': result.resposta.reason,
                'file_sent': result.envio.xml,
                'file_returned': None
            }
