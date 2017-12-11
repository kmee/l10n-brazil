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
    # dt_fim =  fields.Datetime(
    #     string='Data final',
    #     index=True,
    #     required=True,
    # )
    @property
    def versao(self):
        if fields.Datetime.from_string(self.dt_ini) >= datetime.datetime(2016, 1, 1):
            return '011'

        return '009'

    def limpa_formatacao_data(self, data):
        data = data[8:] + data[5:7] + data[:4]
        data = data.replace('-','')
        data = data.replace(' ', '')
        return data.replace('/', '')

    def limpa_formatacao(self, data):
        data = data.replace('-','')
        data = data.replace(' ', '')
        data = data.replace('.', '')
        return data.replace('/', '')

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
        registro_0000.DT_INI = self.limpa_formatacao_data(self.dt_ini[:11]) # data_inicio
        registro_0000.DT_FIN = self.limpa_formatacao_data(self.dt_ini[:11]) # data_final
        registro_0000.NOME = query_resposta[0][0] # filial.razao_social (?)
        registro_0000.CNPJ = self.limpa_formatacao(query_resposta[0][1]) # filial.cnpj_cpf
        registro_0000.UF = query_resposta[0][2] # filial.estado
        registro_0000.IE = query_resposta[0][3] # filial.ie
        registro_0000.COD_MUN = query_resposta[0][4] # filial.municipio_id.codigo_ibge[:7]
        registro_0000.IM = query_resposta[0][5] # filial.im
        registro_0000.SUFRAMA = query_resposta[0][6] # filial.suframa
        registro_0000.IND_PERFIL = 'A' # perfil
        registro_0000.IND_ATIV = '1' # tipo_atividade

        return registro_0000




    def query_registro0100(self):
        quert = """
            select rp.name, rp.street, rp.street2, rp.zip, rp.city
            from res_partner as rp,
        """


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

        arq.read_registro(self.cria_registro(self.query_registro0000()))

        registro_0100 = registros.Registro0100()
        registro_0100.NOME = 'Daniel Sadamo' # contador.nome.strip()
        registro_0100.CPF = '12334532212' # contador.cnpj_cpf.strip() / contador.cnpj_cpf.strip()
        registro_0100.CRC = '123456789012345' # contador.crc.strip()
        """
            contador.cep.strip()
            contador.endereco.strip()
            contador.numero.strip()
            contador.complemento.strip()
            contador.bairro.strip()
            contador.fone.strip()
            contador.fax.strip()
            contador.emeio.strip()
            contador.municipio.ibge()
        """
        registro_0100.END = 'Rua dos ferroviario' #
        registro_0100.NUM = '123'
        registro_0100.COMPL = 'Agonia'
        arq.read_registro(self.cria_registro(registro_0100))

        for bloco in arq._blocos.items():
                for registros_bloco in bloco[1].registros:
                    if not registros_bloco._valores[1] == '9900':
                        registro_9900 = registros.Registro9900()
                        registro_9900.REG_BLC = registros_bloco._valores[1]
                        registro_9900.QTD_REG_BLC = '1'
                        arq.read_registro(self.cria_registro(registro_9900))
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






