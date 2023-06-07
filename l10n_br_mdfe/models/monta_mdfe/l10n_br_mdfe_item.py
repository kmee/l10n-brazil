# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from mdfelib.v3_00 import mdfe as mdfe3
from odoo import models

from ...constants.mdfe import (FISCAL_MODEL_CTE, FISCAL_MODEL_NFE,
                               TRANSPORT_MODALITY_AQUAVIARIO)


class L10nBrMdfeItem(models.Model):
    _inherit = 'l10n_br.mdfe.item'

    def monta_mdfe(self):
        inf_mun_unloading = []

        unloading_cities = self.mapped('receiver_city_id')

        for city in unloading_cities:
            doc = self.filtered(lambda d: d.receiver_city_id == city)

            lista_nfe = []
            lista_cte = []

            for nfe in doc.filtered(
                    lambda f: f.document_id.document_type in FISCAL_MODEL_NFE):
                lista_nfe.append(
                    mdfe3.infNFeType(
                        chNFe=nfe.document_key or '',
                        # SegCodBarra=None,
                        # indReentrega=None,
                        # infUnidTransp=None,
                        # peri=None,
                    )
                )

            for cte in doc.filtered(
                    lambda f: f.document_id.document_type in FISCAL_MODEL_CTE):
                lista_cte.append(
                    mdfe3.infCTeType(
                        chNFe=cte.document_key,
                        # SegCodBarra=None,
                        # indReentrega=None,
                        # infUnidTransp=None,
                        # peri=None,
                    )
                )
            #
            # Somente aquaviario
            #
            inf_mdfe_transporte = None

            if (doc.mdfe_id.transport_modality == TRANSPORT_MODALITY_AQUAVIARIO):
                raise NotImplementedError

            inf_mun_unloading.append(mdfe3.infMunDescargaType(
                cMunDescarga=city.codigo_ibge[:7],
                xMunDescarga=city.name,
                infCTe=lista_cte,
                infNFe=lista_nfe,
                infMDFeTransp=inf_mdfe_transporte,
            ))

        return inf_mun_unloading
