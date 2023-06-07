# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from odoo import models


class L10nBrMdfeSeguro(models.Model):
    _inherit = 'l10n_br.mdfe.insurance'

    def _prepara_resp_type(self):
        pass

    def _prepara_seg_type(self):
        # inf_seg_type = []
        # inf_seg_type.append(
        #     infSegType(
        #         xSeg=record.responsavel_seguro,
        #         CNPJ=misc.punctuation_rm(record.responsavel_cnpj_cpf),
        #     )
        # )
        pass

    def monta_mdfe(self):
        seg = []
        return seg
