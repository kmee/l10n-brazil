# -*- coding: utf-8 -*-
import base64

from sped.efd.icms_ipi import arquivos,registros
from odoo import fields, models, api

class SpedEFD(models.Model):
    _name='sped.efd'

    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        select=True,
    )
    fci_file_sent = fields.Many2one(
        comodel_name='ir.attachment',
        string='Arquivo',
        ondelete='restrict',
        copy=False,
    )
    dt_ini = fields.Datetime(
        string='Data inicial',
        index=True,
        default=fields.Datetime.now,
        required=True,
    )

    def cria_registro(self, registro):
        junta = ''
        for i in range(1, len(registro._valores)):
            junta = junta + '|' + registro._valores[i]
        return junta

    def envia_efd(self):
        arq = arquivos.ArquivoDigital()
        arq.read_registro('|9900|0000|1|')
        arq.read_registro('|9900|9999|1|')
        cont_9900 = 2
        registro_0000 = registros.Registro0000()
        registro_0000.COD_VER = '010'
        registro_0000.COD_FIN = '0'
        registro_0000.DT_INI = '01102016'
        registro_0000.DT_FIN = '30102016'
        registro_0000.NOME = 'KMEE INFORMATICA LTDA'
        registro_0000.CNPJ = '53939351000129'
        registro_0000.UF = 'SP'
        registro_0000.IE = '22222222222222'
        registro_0000.COD_MUN = '1234567'
        registro_0000.IM = '5999'
        registro_0000.SUFRAMA = '123456789'
        registro_0000.IND_PERFIL = 'A'
        registro_0000.IND_ATIV = '1'
        arq.read_registro(self.cria_registro(registro_0000))

        registro_0100 = registros.Registro0100()
        registro_0100.NOME = 'Daniel Sadamo'
        registro_0100.CPF = '12334532212'
        registro_0100.CRC = '123456789012345'
        registro_0100.END = 'Rua dos ferroviario'
        registro_0100.NUM = '123'
        registro_0100.COMPL = 'Agonia'
        arq.read_registro(self.cria_registro(registro_0100))

        for bloco in arq._blocos.items():
                for registros_bloco in bloco[1].registros:
                    if not registros_bloco._valores[1] == '9900':
                        registro_9900 = registros.Registro9900()
                        registro_9900.REG_BLC = registros_bloco._valores[1]
                        registro_9900.QTD_REG_BLC = '1'
                        arq._blocos['9'].add(registro_9900)
                    else:
                        cont_9900 = cont_9900 + 1

        registro_9900 = registros.Registro9900()
        registro_9900.REG_BLC = '9900'
        registro_9900.QTD_REG_BLC = str(cont_9900+1)
        arq.read_registro(self.cria_registro(registro_9900))

        arquivo = self.env['ir.attachment']


        dados = {
            'name': 'teste.txt',
            'datas_fname': 'teste.txt',
            'res_model': 'sped.efd',
            'res_id': self.id,
            'datas': base64.b64encode(arq.getstring().encode('utf-8')),
            'mimetype':'application/txt'
        }
        arquivo.create(dados)






