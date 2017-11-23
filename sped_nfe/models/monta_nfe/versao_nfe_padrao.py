# -*- coding: utf-8 -*-
#
# Copyright 2017 Taŭga Tecnologia
#   Aristides Caldeira <aristides.caldeira@tauga.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from __future__ import division, print_function, unicode_literals

import logging

_logger = logging.getLogger(__name__)

try:
    from pysped.nfe.leiaute import *

except (ImportError, IOError) as err:
    _logger.debug(err)


ClasseProcNFe = ProcNFe_310
#
# Cabeçalho
#
ClasseNFe = NFe_310
ClasseNFCe = NFCe_310

#
# Itens
#
ClasseDet = Det_310
# ClasseRastro = Rastro_310
ClasseDI = DI_310
ClasseAdi = Adi_310

#
# Transporte
#
ClasseReboque = Reboque_310
ClasseVol = Vol_310

#
# Documentos referenciados
#
ClasseNFRef = NFRef_310

#
# Parcelamento e pagamento
#
ClasseDup = Dup_310
# ClassePag = Pag_310
