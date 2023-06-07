# Copyright 2018 KMEE INFORMATICA LTDA, Grupo Zenir
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import tempfile

from erpbrasil.base import misc
from odoo import fields, models
from pynfe.processamento.comunicacao import ComunicacaoMDFe


class ConsultaMDFe(models.Model):
    _name = 'consulta.mdfe'

    _inherit = 'l10n_br_fiscal.document.mixin'

    query_type = fields.Selection(
        selection=[
            ('not_closed', 'Not closed'),
            ('other', 'Other'),
        ],
        string='Query type',
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Empresa',
        default=lambda self: self.env.company_id,
        inverse='_inverse_company_id',
    )

    certificate_id = fields.Many2one(
        comodel_name='sped.certificado',
        string='Certificado digital',
        default=lambda self: self.company_id.certificado_id.id,
    )

    query_message = fields.Text(
        string='Query return'
    )

    mdfe_not_closed = fields.Many2many(
        comodel_name='l10n_br_fiscal.document',
        string='MDF-e not closed',
    )

    comment_ids = fields.Many2many(
        comodel_name="l10n_br_fiscal.comment",
        relation="l10n_br_fiscal_document_mixin_comment_rel1",
        column1="document_mixin_id",
        column2="comment_id",
        string="Comments",
        domain=[("object", "=", "l10n_br_fiscal.document.mixin")],
    )

    def _inverse_company_id(self):
        if self.company_id:
            self.certificate_id = self.company_id.certificado_id

    def consultar(self):
        if not (self.company_id and self.certificate_id):
            return {}
        if self.query_type == 'not_closed':
            caminho = tempfile.gettempdir() + '/certificado.pfx'
            f = open(caminho, 'wb')
            f.write(self.certificate_id.arquivo.decode('base64'))
            f.close()

            mdfe = ComunicacaoMDFe(self.company_id.estado, caminho,
                                   self.certificate_id.senha, True)
            process = mdfe.consulta_not_closed(
                misc.punctuation_rm(self.company_id.cnpj_cpf_numero))
            message = 'Return code: ' + \
                process.resposta.cStat
            message += '\nMessage: ' + \
                process.resposta.xMotivo.encode('utf-8')
            self.query_message = message
            self.mdfe_not_closed = [(5, 0, 0)]
            for infMDFe in process.resposta.infMDFe:
                doc = self.env['l10n_br_fiscal.document'].search([
                    ('document_key', '=', infMDFe.chMDFe)])
                if doc:
                    doc.authorization_protocol = infMDFe.nProt
                self.mdfe_not_closed += doc
            if process.resposta.cStat == '112':
                self.mdfe_not_closed = [(5, 0, 0)]
