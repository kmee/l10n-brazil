# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
#
# Concrete EFD ICMS/IPI registers and their mappings from Odoo transactions.
#
# Each concrete register inherits its generated abstract spec from
# sped_efd_icms_ipi_spec_20.py and implements the mapping hooks defined by
# l10n_br_sped.mixin: _odoo_model + _odoo_domain (or _odoo_query) to select
# the Odoo records, and _map_from_odoo to convert each record into the SPED
# register values. New blocks are added here phase by phase.

import textwrap

from erpbrasil.base import misc

from odoo import api, fields, models

LAYOUT_VERSION_CODE = "020"


class Registro0000(models.Model):
    "Abertura do Arquivo Digital e Identificação da entidade"

    _description = textwrap.dedent(f"    {__doc__}")
    _name = "l10n_br_sped.efd_icms_ipi.0000"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0000"]
    _odoo_model = "res.company"

    COD_FIN = fields.Selection(
        selection=[
            ("0", "0 - Remessa do arquivo original"),
            ("1", "1 - Remessa do arquivo substituto"),
        ],
        string="Finalidade do arquivo",
        default="0",
    )

    IND_PERFIL = fields.Selection(
        selection=[
            ("A", "A - Perfil A"),
            ("B", "B - Perfil B"),
            ("C", "C - Perfil C"),
        ],
        string="Perfil de apresentação do arquivo fiscal",
        default="A",
    )

    IND_ATIV = fields.Selection(
        selection=[
            ("0", "0 - Industrial ou equiparado a industrial"),
            ("1", "1 - Outros"),
        ],
        string="Indicador de tipo de atividade",
        default="0",
    )

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        return [("id", "=", declaration.company_id.id)]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        # DT_INI / DT_FIN come from the declaration fields directly.
        return {
            "COD_VER": LAYOUT_VERSION_CODE,
            "COD_FIN": "0",
            "NOME": record.legal_name or record.name,
            "CNPJ": misc.punctuation_rm(record.vat or ""),
            "UF": record.state_id.code or "",
            "IE": record.l10n_br_ie_code or "",
            "COD_MUN": record.city_id.ibge_code or "",
            "IM": record.l10n_br_im_code or "",
            "SUFRAMA": record.l10n_br_isuf_code or "",
            "IND_PERFIL": "A",
            "IND_ATIV": "0",
        }
