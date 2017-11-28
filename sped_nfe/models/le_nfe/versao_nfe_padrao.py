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
    # from pysped.nfe.leiaute import *
    from pysped.nfe.leiaute import ( ProcNFe_400,
                                     NFe_400,
                                     NFCe_400,
                                     Det_400,
                                     DI_400,
                                     Adi_400,
                                     Reboque_400,
                                     Vol_400,
                                     NFRef_400,
                                     Dup_400,
                                     Pag_400,
                                     Rastro_400
                                     )

except ImportError:
    from pysped.nfe.leiaute import ( ProcNFe_310 as ProcNFe_400,
                                     NFe_310 as NFe_400,
                                     NFCe_310 as NFCe_400,
                                     Det_310 as Det_400,
                                     DI_310 as DI_400,
                                     Adi_310 as Adi_400,
                                     Reboque_310 as Reboque_400,
                                     Vol_310 as Vol_400,
                                     NFRef_310 as NFRef_400,
                                     Dup_310 as Dup_400
                                     )

except (IOError) as err:
    _logger.debug(err)


ClasseProcNFe = ProcNFe_400
#
# Cabeçalho
#
ClasseNFe = NFe_400
ClasseNFCe = NFCe_400

#
# Itens
#
ClasseDet = Det_400

try:
    ClasseRastro = Rastro_400
except Exception as err:
    _logger.debug(err)

ClasseDI = DI_400
ClasseAdi = Adi_400

#
# Transporte
#
ClasseReboque = Reboque_400
ClasseVol = Vol_400

#
# Documentos referenciados
#
ClasseNFRef = NFRef_400

#
# Parcelamento e pagamento
#
ClasseDup = Dup_400

try:
    ClassePag = Pag_400
except Exception as err:
    _logger.debug(err)
