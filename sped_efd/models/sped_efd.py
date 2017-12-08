# -*- coding: utf-8 -*-
import base64

from sped.efd.icms_ipi import arquivos,blocos,registros
from odoo import fields, models, api


# erro no bloco 0990 deve ser 4
# erro no bloco 9990 deve ser 3
# erro no bloco 9001 deve ser 0

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

    def envia_efd(self):
        txt = u"""|0000|010|0|01102016|30102016|KMEE INFORMATICA LTDA|53.939.351/0001-29|333.333.333-33|SP|222.222.222.222|1234567|5999|0123|A|1|
        |0001|0|
        |0100|Daniel Sadamo|12334532212|532212|||Rua dos ferroviario|123|Agonia||||||
        |0990|3|
        |C001|1|
        |C990|2|
        |D001|1|
        |D990|2|
        |E001|1|
        |E990|2|
        |G001|1|
        |G990|2|
        |H001|1|
        |H990|2|
        |K001|1|
        |K990|2|
        |1001|1|
        |1990|2|
        |9001|1|
        |9990|2|
        |9999|21|
        """.replace('\n', '\r\n')
        arq = arquivos.ArquivoDigital()

        arq._registro_abertura.COD_VER = '010'
        arq._registro_abertura.COD_FIN = '0'
        arq._registro_abertura.DT_INI = '01102016'
        arq._registro_abertura.DT_FIN = '30102016'
        arq._registro_abertura.NOME = 'KMEE INFORMATICA LTDA'
        arq._registro_abertura.CNPJ = '53939351000129'
        # arq._registro_abertura.CPF = '333.333.333-33'
        arq._registro_abertura.UF = 'SP'
        arq._registro_abertura.IE = '22222222222222'
        arq._registro_abertura.COD_MUN = '1234567'
        arq._registro_abertura.IM = '5999'
        arq._registro_abertura.SUFRAMA = '123456789' # 9 digitos
        arq._registro_abertura.IND_PERFIL = 'A'
        arq._registro_abertura.IND_ATIV = '1'

        contabilista = registros.Registro0100()
        contabilista.NOME = 'Daniel Sadamo'
        contabilista.CPF = '12334532212'
        contabilista.CRC = '123456789012345'
        contabilista.END = 'Rua dos ferroviario'
        contabilista.NUM = '123'
        contabilista.COMPL = 'Agonia'
        arquivo = self.env['ir.attachment']

        arq._blocos['0'].add(contabilista)
        fechamento = registros.Registro0990()
        fechamento.QTD_LIN_0 = 4
        dados = {
            'name': 'teste.txt',
            'datas_fname': 'teste.txt',
            'res_model': 'sped.efd',
            'res_id': self.id,
            'datas': base64.b64encode(arq.getstring().encode('utf-8')),
            'mimetype':'application/txt'
        }
        arquivo.create(dados)






