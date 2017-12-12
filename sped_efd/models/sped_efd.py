# -*- coding: utf-8 -*-
import base64
import datetime

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
    dt_fim =  fields.Datetime(
        string='Data final',
        index=True,
        required=True,
    )

    @property
    def versao(self):
        if fields.Datetime.from_string(self.dt_ini) >= datetime.datetime(2016, 1, 1):
            return '011'

        return '009'

    def transforma_data(self, data): # aaaammdd
        data = self.limpa_formatacao(data)
        return data[6:] + data[4:6] + data[:4]

    def limpa_formatacao(self, data):
        replace = ['-',' ','(',')','/','.']
        for i in replace:
            data = data.replace(i,'')
        return data

    def query_registro0000(self):
        query = """
            select DISTINCT 
                p.nome, p.cnpj_cpf, m.estado, p.ie, m.codigo_anp, p.im, p.suframa
            from 
                sped_documento as d 
                join sped_empresa as e on d.empresa_id=e.id
                join sped_participante as p on e.participante_id=p.id 
                join sped_municipio as m on m.id=p.municipio_id;
        """
        self._cr.execute(query)
        query_resposta = self._cr.fetchall()

        registro_0000 = registros.Registro0000()
        registro_0000.COD_VER = str(self.versao)
        registro_0000.COD_FIN = '0' # finalidade
        registro_0000.DT_INI = self.transforma_data(self.dt_ini[:10]) # data_inicio
        registro_0000.DT_FIN = self.transforma_data(self.dt_fim[:10]) # data_final
        registro_0000.NOME = query_resposta[0][0] # filial.razao_social (?)
        cpnj_cpf = self.limpa_formatacao(query_resposta[0][1])
        if cpnj_cpf == 11:
            registro_0000.CPF = cpnj_cpf
        else:
            registro_0000.CNPJ = cpnj_cpf
        registro_0000.UF = query_resposta[0][2] # filial.estado
        registro_0000.IE = query_resposta[0][3] # filial.ie
        registro_0000.COD_MUN = query_resposta[0][4] # filial.municipio_id.codigo_ibge[:7]
        registro_0000.IM = query_resposta[0][5] # filial.im
        registro_0000.SUFRAMA = query_resposta[0][6] # filial.suframa
        registro_0000.IND_PERFIL = 'A' # perfil
        registro_0000.IND_ATIV = '1' # tipo_atividade

        return registro_0000

    def query_registro0100(self):
        query = """
            select distinct 
            p.nome, p.cnpj_cpf, p.cep, p.endereco, p.numero, p.complemento,
            p.bairro, p.fone, p.email, m.codigo_anp, p.crc
            from 
            sped_participante as p 
            join sped_municipio as m on p.municipio_id=m.id
        """
        self._cr.execute(query)
        query_resposta = self._cr.fetchall()

        registro_0100 = registros.Registro0100()
        registro_0100.NOME = query_resposta[0][0]
        cpnj_cpf = self.limpa_formatacao(query_resposta[0][1])
        if cpnj_cpf == 11:
            registro_0100.CPF = cpnj_cpf
        else:
            registro_0100.CNPJ = cpnj_cpf
        registro_0100.CRC = query_resposta[0][10]
        registro_0100.CEP = self.limpa_formatacao(query_resposta[0][2])
        registro_0100.END = query_resposta[0][3]
        registro_0100.NUM = query_resposta[0][4]
        registro_0100.COMPL = query_resposta[0][5]
        registro_0100.BAIRRO = query_resposta[0][6]
        registro_0100.FONE = self.limpa_formatacao(query_resposta[0][7])
        registro_0100.EMAIL = query_resposta[0][8]
        registro_0100.COD_MUN = query_resposta[0][9]

        return registro_0100

    def query_registro1010(self):
        registro1010 = registros.Registro1010()
        registro1010.IND_EXP = 'S'
        registro1010.IND_CCRF = 'S'
        registro1010.IND_COMB = 'S'
        registro1010.IND_USINA = 'S'
        registro1010.IND_VA = 'S'
        registro1010.IND_EE = 'S'
        registro1010.IND_CART = 'S'
        registro1010.IND_FORM = 'S'
        registro1010.IND_AER = 'S'

        return registro1010

    def junta_pipe(self, registro):
        junta = ''
        for i in range(1, len(registro._valores)):
            junta = junta + '|' + registro._valores[i]
        return junta

    def envia_efd(self):
        arq = arquivos.ArquivoDigital()
        arq.read_registro('|9900|0000|1|')
        arq.read_registro('|9900|9999|1|')
        cont_9900 = 2

        # bloco 0
        arq.read_registro(self.junta_pipe(self.query_registro0000()))
        arq.read_registro(self.junta_pipe(self.query_registro0100()))

        # bloco 1
        arq.read_registro(self.junta_pipe(self.query_registro1010()))

        for bloco in arq._blocos.items():
                for registros_bloco in bloco[1].registros:
                    if not registros_bloco._valores[1] == '9900':
                        registro_9900 = registros.Registro9900()
                        registro_9900.REG_BLC = registros_bloco._valores[1]
                        registro_9900.QTD_REG_BLC = '1'
                        arq.read_registro(self.junta_pipe(registro_9900))
                    else:
                        cont_9900 = cont_9900 + 1

        registro_9900 = registros.Registro9900()
        registro_9900.REG_BLC = '9900'
        registro_9900.QTD_REG_BLC = str(cont_9900+1)
        arq.read_registro(self.junta_pipe(registro_9900))

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






