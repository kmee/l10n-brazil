MDFE_ENVIRONMENT = (
    ('1', u'Produção'),
    ('2', u'Homologação'),
)

MDFE_ENVIRONMENT_PRODUCAO = '1'

TRANSPORT_MODALITY = (
    ('1', u'Rodoviário'),
    ('2', u'Aéreo'),
    ('3', u'Aquaviário'),
    ('4', u'Ferroviário')
)
TRANSPORT_MODALITY_RODOVIARIO = '1'
TRANSPORT_MODALITY_AQUAVIARIO = '3'

FISCAL_MODEL = (
    # ('MERCADORIAS E SERVIÇOS', (
    ('65', u'NFC-e - 65'),
    ('2D', u'CF por impressora fiscal - 2D'),
    ('2C', u'CF por ponto de venda (PDV) - 2C'),
    ('2B', u'CF por máquina registradora - 2B'),
    ('59', u'CF-e - 59'),
    ('60', u'CF-e ECF - 60'),
    ('01', u'NF - 01 E 1A'),
    ('1B', u'NF avulsa - 1B'),
    ('04', u'NF de produtor rural - 04'),
    ('21', u'NF de serv. de comunicação - 21'),
    ('22', u'NF de serv. de telecomunicação - 22'),
    ('07', u'NF de serv. de transporte - 07'),
    ('27', u'NF de transp. ferroviário de cargas - 27'),
    ('02', u'NF de venda a consumidor - 02'),
    ('55', u'NF-e - 55'),
    ('06', u'NF/conta de energia elétrica - 06'),
    ('29', u'NF/conta de fornec. de água canalizada - 29'),
    ('28', u'NF/conta de fornec. de gás canalizado - 28'),
    ('18', u'CF - resumo de movimento diário - 18'),
    ('23', u'GNRE - 23'),
    #
    # Modelos não oficiais
    #
    ('SC', u'NFS - SC'),
    ('SE', u'NFS-e - SE'),
    ('RL', u'Recibo de locação - RL'),
    ('XX', u'Outros documentos não fiscais - XX'),
    ('TF', u'Atualização de tabela de fornecedor'),
    # )),
    # ('TRANSPORTE', (
    ('24', u'Autorização de carregamento e transporte - 24'),
    ('14', u'Bilhete de passagem aquaviário - 14'),
    ('15', u'Bilhete de passagem e nota de bagagem -15'),
    ('2E', u'Bilhete de passagem emitido por ECF - 2E'),
    ('16', u'Bilhete de passagem ferroviário - 16'),
    ('13', u'Bilhete de passagem rodoviário - 13'),
    ('30', u'Bilhete/recibo do passageiro - 30'),
    ('10', u'Conhecimento aéreo - 10'),
    ('09', u'Conhec. de transporte aquaviário de cargas - 09'),
    ('8B', u'Conhec. de transporte de cargas avulso - 8B'),
    ('57', u'CT-e - 57'),
    ('11', u'Conhec. de transporte ferroviário de cargas - 11'),
    ('26', u'Conhec. de transporte multimodal de cargas - 26'),
    ('08', u'Conhec. de transporte rodoviário de cargas - 08'),
    ('17', u'Despacho de transporte - 17'),
    ('25', u'Manifesto de carga - 25'),
    ('20', u'Ordem de coleta de carga - 20'),
    # )),
)

FISCAL_MODEL_CTE = '57'
FISCAL_MODEL_MDFE = '58'
FISCAL_MODEL_NFE = '55'

RESPONSIBLE_INSURANCE = (
    ('1', u'Emitente do MDFe'),
    ('22', u'Responsável pela contratação do serviço de transporte(contratante)')
)

SITUATION_NFE = (
    ('em_digitacao', 'Em digitação'),
    ('a_enviar', 'Aguardando envio'),
    ('enviada', 'Aguardando processamento'),
    ('rejeitada', 'Rejeitada'),
    ('autorizada', 'Autorizada'),
    ('cancelada', 'Cancelada'),
    ('denegada', 'Denegada'),
    ('inutilizada', 'Inutilizada'),
    ('encerrada', 'Encerrada'),
)

SITUATION_NFE_A_ENVIAR = 'a_enviar'
SITUATION_NFE_AUTORIZADA = 'autorizada'
SITUATION_NFE_CANCELADA = 'cancelada'
SITUATION_NFE_EM_DIGITACAO = 'em_digitacao'
SITUATION_NFE_ENVIADA = 'enviada'
SITUATION_NFE_REJEITADA = 'rejeitada'
SITUATION_MDFE_ENCERRADA = 'encerrada'

STATUS_MDFE = {
    '100' : 'autorizada',
    '101' : 'cancelada',
    '132' : 'encerrada',
}

BODY_TYPE = (
    ('00', u'não aplicável'),
    ('01', u'Aberta'),
    ('02', u'Fechada/Baú'),
    ('03', u'Granelera'),
    ('04', u'Porta Container'),
    ('05', u'Sider')
)

EMISSION_TYPE_MDFE = (
    ('1', u'Normal'),
    ('2', u'Contingência Off-Line'),
    ('3', u'Regime Especial NFF')
)

EMISSION_TYPE_MDFE_NORMAL = '1'
EMISSION_TYPE_MDFE_CONTINGENCIA = '2'
EMISSION_TYPE_MDFE_PROPRIA = '3'

EMITTER_TYPE = (
    ('1', u'Prestador de serviço de transporte'),
    ('2', u'Transportador de Carga Própria'),
    ('3', u'Prestador de serviço de transporte que emitirá CTe Globalizado')
)

WHEELED_TYPE = (
    ('01', u'Truck'),
    ('02', u'Toco'),
    ('03', u'Cavalo Mecânico'),
    ('04', u'VAN'),
    ('05', u'Utilitário'),
    ('06', u'Outros')
)

TRANSPORTER_TYPE = (
    ('1' u'ETC'),
    ('2' u'TAC'),
    ('3', u'CTC')
)
