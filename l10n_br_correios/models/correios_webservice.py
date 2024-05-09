from odoo import _, api, models
from odoo.exceptions import ValidationError

# O acesso as APIs, deve ser realizada pelo catálogo do Correios API. No catálogo o
# cliente poderá testar e acompanhar as mudanças quando houver. O catálogo está
# disponível no ambiente de Homologação e Produção:
#           - Homologação: https://cwshom.correios.com.br/
#           - Produção: https://cws.correios.com.br/

URL_SERVICE = [
    {"producao":""},
    {"homologacao":"https://apihom.correios.com.br"}
]

URL_TOKEN = [
    {"producao":""},
    {"homologacao":""}
]

class CorreiosWebService(models.Model):
    _name = "l10n_br_correios.webservice"
    _description = "Correios Webservice"
    
    @api.model
    def get_token(self):
        pass
    
    @api.model
    def api_agencia(self):
        pass
    
    @api.model
    def api_prazo(self):
        pass
    
    @api.model
    def api_preco(self):
        pass
    
    @api.model
    def api_rastro(self):
        pass
    
    