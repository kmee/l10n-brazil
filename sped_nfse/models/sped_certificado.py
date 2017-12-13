# -*- coding: utf-8 -*-
#
# Copyright 2017 KMEE INFORMATICA
#   Daniel Sadamo <daniel.sadamo@kmee.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

import base64
import logging
import tempfile

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

try:
    import pybrasil.certificado as Cert
    from pytrustnfe.certificado import Certificado as CertificadoNFse
except (ImportError, IOError) as err:
    _logger.debug(err)


CERTIFICADOS = {}


class SpedCertificado(models.Model):
    _inherit = 'sped.certificado'

    def certificado_nfse(self):
        self.ensure_one()
        cert = self.certificado_nfe()

        senha = bytes(cert.senha.encode())
        arquivo = cert.stream_certificado

        return CertificadoNFse(arquivo, senha)
