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
from lxml.builder import E

from odoo import api, fields, models

LAYOUT_VERSION_CODE = "020"

# Fiscal document model codes routed to specific blocks.
CTE_MODELS = ["57", "67"]  # transport (Bloco D)
UTILITY_MODELS = ["06", "28", "29", "66"]  # energy/water/gas (Bloco C500)


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

    # Configuration used to populate the mandatory registers 0002 and 0100,
    # which have no direct Odoo source.
    CLAS_ESTAB_IND = fields.Selection(
        selection=[
            ("00", "00 - Industrial - Transformação"),
            ("01", "01 - Industrial - Beneficiamento"),
            ("02", "02 - Industrial - Montagem"),
            ("03", "03 - Industrial - Acondicionamento/Reacondicionamento"),
            ("04", "04 - Industrial - Renovação/Recondicionamento"),
            ("05", "05 - Equiparado a Industrial - Por opção"),
            ("06", "06 - Equiparado a Industrial - Importação de bens"),
            ("07", "07 - Equiparado a Industrial - Filial de estab. industrial"),
            ("08", "08 - Equiparado a Industrial - Outros"),
            ("09", "09 - Não Industrial / Não equiparado"),
        ],
        string="Classificação do estabelecimento industrial (Reg. 0002)",
    )

    accountant_id = fields.Many2one(
        comodel_name="res.partner",
        string="Contabilista (Reg. 0100)",
    )

    accountant_crc = fields.Char(string="CRC do contabilista (Reg. 0100)")

    ind_apur = fields.Selection(
        selection=[("0", "0 - Mensal"), ("1", "1 - Decendial")],
        string="Indicador da apuração do IPI",
        default="0",
    )

    ind_tp_leiaute = fields.Selection(
        selection=[
            ("0", "0 - Leiaute simplificado"),
            ("1", "1 - Leiaute completo (K200, K230, etc.)"),
            ("2", "2 - Leiaute restrito aos saldos de estoque (K200)"),
        ],
        string="Tipo de leiaute do Bloco K (Reg. K010)",
        default="2",
    )

    @api.model
    def _append_top_view_elements(self, group, inline=False):
        res = super()._append_top_view_elements(group, inline=inline)
        group.append(E.field(name="accountant_id"))
        group.append(E.field(name="accountant_crc"))
        group.append(E.field(name="ind_apur"))
        group.append(E.field(name="ind_tp_leiaute"))
        return res

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

    def button_populate_sped_from_odoo(self):
        # Populate the declaration's own 0000 fields from the company before
        # pulling the child registers, so the file header is complete without
        # relying on the form onchange (which does not fire on create/headless).
        for declaration in self:
            if declaration.company_id:
                declaration.write(
                    declaration._map_from_odoo(
                        declaration.company_id, None, declaration
                    )
                )
        return super().button_populate_sped_from_odoo()


# ---------------------------------------------------------------------------
# Concrete register stubs (one per spec register so the inter-register
# relations resolve). Mappings are added block by block by overriding
# _odoo_model + _odoo_domain/_odoo_query and _map_from_odoo.
# ---------------------------------------------------------------------------


class Registro0002(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0002"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0002"]
    _odoo_model = "res.company"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        # Mandatory only for industrial establishments: emitted when the
        # classification is set on the declaration (register 0000).
        if declaration.CLAS_ESTAB_IND:
            return [("id", "=", declaration.company_id.id)]
        return [("id", "in", [])]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {"CLAS_ESTAB_IND": declaration.CLAS_ESTAB_IND}


class Registro0005(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0005"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0005"]
    _odoo_model = "res.company"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        return [("id", "=", declaration.company_id.id)]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {
            "FANTASIA": record.name,
            "CEP": misc.punctuation_rm(record.zip or ""),
            "END": record.street_name or "",
            "NUM": record.street_number or "",
            "COMPL": record.street2 or "",
            "BAIRRO": record.district or "",
            "FONE": misc.punctuation_rm(record.phone or "") if record.phone else "",
            "FAX": "",
            "EMAIL": record.email or "",
        }


class Registro0015(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0015"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0015"]


class Registro0100(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0100"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0100"]
    _odoo_model = "res.partner"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        if declaration.accountant_id:
            return [("id", "=", declaration.accountant_id.id)]
        return [("id", "in", [])]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        digits = misc.punctuation_rm(record.cnpj_cpf_stripped or "")
        return {
            "NOME": record.legal_name or record.name,
            "CPF": "" if record.is_company else digits,
            "CRC": declaration.accountant_crc or "",
            "CNPJ": digits if record.is_company else "",
            "CEP": misc.punctuation_rm(record.zip or ""),
            "END": record.street or "",
            "NUM": "",
            "COMPL": record.street2 or "",
            "BAIRRO": record.district or "",
            "FONE": misc.punctuation_rm(record.phone or "") if record.phone else "",
            "FAX": "",
            "EMAIL": record.email or "",
            "COD_MUN": record.city_id.ibge_code or "",
        }


class Registro0150(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0150"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0150"]
    _odoo_model = "res.partner"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        return [("id", "in", declaration.fiscal_document_partner_ids.ids)]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        digits = misc.punctuation_rm(record.cnpj_cpf_stripped or "")
        return {
            "COD_PART": str(record.id),
            "NOME": record.legal_name or record.name,
            "COD_PAIS": record.country_id.ibge_code or "",
            "CNPJ": digits if record.is_company else "",
            "CPF": "" if record.is_company else digits,
            "IE": record.l10n_br_ie_code or "",
            "COD_MUN": record.city_id.ibge_code or "",
            "SUFRAMA": record.l10n_br_isuf_code or "",
            "END": record.street or "",
            "NUM": "",
            "COMPL": record.street2 or "",
            "BAIRRO": record.district or "",
        }


class Registro0175(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0175"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0175"]


class Registro0190(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0190"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0190"]
    _odoo_model = "uom.uom"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        return [("id", "in", declaration.fiscal_uom_ids.ids)]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {
            "UNID": record.code or record.name,
            "DESCR": record.description or record.name,
        }


class Registro0200(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0200"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0200"]
    _odoo_model = "product.product"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        return [("id", "in", declaration.fiscal_product_ids.ids)]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {
            "COD_ITEM": record.default_code or str(record.id),
            "DESCR_ITEM": record.name,
            "COD_BARRA": record.barcode or "",
            "COD_ANT_ITEM": "",
            "UNID_INV": record.uom_id.code or record.uom_id.name,
            "TIPO_ITEM": "00",
            "COD_NCM": misc.punctuation_rm(record.ncm_id.code or ""),
            "EX_IPI": "",
            "COD_GEN": record.fiscal_genre_code or "",
            "COD_LST": "",
            "ALIQ_ICMS": "",
            "CEST": misc.punctuation_rm(record.cest_id.code or ""),
        }


class Registro0205(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0205"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0205"]


class Registro0206(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0206"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0206"]


class Registro0210(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0210"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0210"]


class Registro0220(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0220"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0220"]

    @api.model
    def _odoo_query(self, parent_record, declaration):
        # Distinct commercial UoMs used for this product (register 0200) in the
        # period that differ from its inventory UoM, so the conversion factor to
        # the inventory unit can be declared.
        query = """
            SELECT DISTINCT line.uom_id AS uom_id
            FROM l10n_br_fiscal_document_line line
            JOIN l10n_br_fiscal_document doc ON doc.id = line.document_id
            WHERE line.product_id = %s
              AND line.uom_id IS NOT NULL
              AND line.uom_id != %s
              AND doc.company_id = %s
              AND doc.document_date >= %s
              AND doc.document_date <= %s
              AND doc.state_edoc = 'autorizada'
        """
        params = [
            parent_record.id,
            parent_record.uom_id.id,
            declaration.company_id.id,
            declaration.DT_INI,
            declaration.DT_FIN,
        ]
        return query, params

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        commercial_uom = self.env["uom.uom"].browse(record["uom_id"])
        inventory_uom = parent_record.uom_id
        if commercial_uom.category_id == inventory_uom.category_id:
            factor = commercial_uom._compute_quantity(1.0, inventory_uom)
        else:
            factor = 1.0
        return {
            "UNID_CONV": commercial_uom.code or commercial_uom.name,
            "FAT_CONV": factor,
            "COD_BARRA": "",
        }


class Registro0221(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0221"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0221"]


class Registro0300(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0300"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0300"]


class Registro0305(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0305"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0305"]


class Registro0400(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0400"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0400"]
    _odoo_model = "l10n_br_fiscal.operation"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        return [("id", "in", declaration.fiscal_operation_ids.ids)]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {
            "COD_NAT": record.code or str(record.id),
            "DESCR_NAT": record.name,
        }


class Registro0450(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0450"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0450"]
    _odoo_model = "l10n_br_fiscal.comment"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        return [("id", "in", declaration.fiscal_comment_ids.ids)]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {
            "COD_INF": str(record.id),
            "TXT": record.comment or "",
        }


class Registro0460(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0460"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0460"]


class Registro0500(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0500"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0500"]


class Registro0600(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.0600"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.0600"]


class Registrob020(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.b020"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.b020"]


class Registrob025(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.b025"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.b025"]


class Registrob030(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.b030"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.b030"]


class Registrob035(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.b035"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.b035"]


class Registrob350(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.b350"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.b350"]


class Registrob420(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.b420"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.b420"]


class Registrob440(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.b440"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.b440"]


class Registrob460(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.b460"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.b460"]


class Registrob470(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.b470"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.b470"]


class Registrob500(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.b500"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.b500"]


class Registrob510(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.b510"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.b510"]


class Registroc100(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c100"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c100"]
    _odoo_model = "l10n_br_fiscal.document"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        # Goods documents only: transport (Bloco D) and utilities (C500) excluded.
        return [
            ("id", "in", declaration.fiscal_document_ids.ids),
            ("document_type_id.code", "not in", CTE_MODELS + UTILITY_MODELS),
        ]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        # Reform note (layout 020): C100 carries ICMS/IPI only; CBS/IBS/IS are
        # excluded from the EFD amounts, so only the fiscal totals are mapped.
        return {
            "IND_OPER": "0" if record.fiscal_operation_type == "in" else "1",
            "IND_EMIT": "0" if record.issuer == "company" else "1",
            "COD_PART": str(record.partner_id.id),
            "COD_MOD": record.document_type_id.code,
            "COD_SIT": record.state_fiscal,
            "SER": record.document_serie,
            "NUM_DOC": misc.punctuation_rm(str(record.document_number or "")),
            "CHV_NFE": record.document_key or "",
            "DT_DOC": record.document_date,
            "DT_E_S": record.date_in_out,
            "VL_DOC": record.fiscal_amount_total,
            "IND_PGTO": "",
            "VL_DESC": record.amount_discount_value,
            "VL_ABAT_NT": record.amount_financial_discount_value,
            "VL_MERC": record.amount_price_gross,
            "IND_FRT": "9",
            "VL_FRT": record.amount_freight_value,
            "VL_SEG": record.amount_insurance_value,
            "VL_OUT_DA": record.amount_other_value,
            "VL_BC_ICMS": record.amount_icms_base,
            "VL_ICMS": record.amount_icms_value,
            "VL_BC_ICMS_ST": record.amount_icmsst_base,
            "VL_ICMS_ST": record.amount_icmsst_value,
            "VL_IPI": record.amount_ipi_value,
            "VL_PIS": record.amount_pis_value,
            "VL_COFINS": record.amount_cofins_value,
        }


class Registroc101(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c101"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c101"]


class Registroc105(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c105"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c105"]


class Registroc110(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c110"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c110"]


class Registroc111(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c111"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c111"]


class Registroc112(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c112"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c112"]


class Registroc113(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c113"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c113"]


class Registroc114(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c114"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c114"]


class Registroc115(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c115"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c115"]


class Registroc116(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c116"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c116"]


class Registroc120(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c120"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c120"]


class Registroc130(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c130"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c130"]


class Registroc140(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c140"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c140"]


class Registroc141(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c141"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c141"]


class Registroc160(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c160"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c160"]


class Registroc165(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c165"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c165"]


class Registroc170(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c170"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c170"]

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        return [("document_id", "=", parent_record.id)]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        cst_icms = f"{record.icms_origin or '0'}{record.icms_cst_code or '00'}"
        return {
            "NUM_ITEM": index + 1,
            "COD_ITEM": record.product_id.default_code or str(record.product_id.id),
            "DESCR_COMPL": record.name or "",
            "QTD": record.fiscal_quantity,
            "UNID": record.uom_id.code or record.uom_id.name,
            "VL_ITEM": record.price_gross or 0.0,
            "VL_DESC": record.discount_value,
            "IND_MOV": "0" if record.cfop_id.stock_move else "1",
            "CST_ICMS": cst_icms,
            "CFOP": str(record.cfop_id.code or ""),
            "COD_NAT": record.fiscal_operation_id.code or "",
            "VL_BC_ICMS": record.icms_base,
            "ALIQ_ICMS": record.icms_percent,
            "VL_ICMS": record.icms_value,
            "VL_BC_ICMS_ST": record.icmsst_base,
            "ALIQ_ST": record.icmsst_percent,
            "VL_ICMS_ST": record.icmsst_value,
            "IND_APUR": declaration.ind_apur,
            "CST_IPI": record.ipi_cst_code or "",
            "COD_ENQ": record.ipi_guideline_id.code or "",
            "VL_BC_IPI": record.ipi_base,
            "ALIQ_IPI": record.ipi_percent,
            "VL_IPI": record.ipi_value,
            "CST_PIS": record.pis_cst_code or "",
            "VL_BC_PIS": record.pis_base,
            "ALIQ_PIS": record.pis_percent,
            "QUANT_BC_PIS": 0.0,
            "VL_PIS": record.pis_value,
            "CST_COFINS": record.cofins_cst_code or "",
            "VL_BC_COFINS": record.cofins_base,
            "ALIQ_COFINS": record.cofins_percent,
            "QUANT_BC_COFINS": 0.0,
            "VL_COFINS": record.cofins_value,
            "COD_CTA": "",
            "VL_ABAT_NT": record.financial_discount_value,
        }


class Registroc171(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c171"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c171"]


class Registroc172(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c172"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c172"]


class Registroc173(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c173"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c173"]


class Registroc174(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c174"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c174"]


class Registroc175(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c175"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c175"]


class Registroc176(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c176"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c176"]


class Registroc177(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c177"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c177"]


class Registroc178(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c178"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c178"]


class Registroc179(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c179"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c179"]


class Registroc180(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c180"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c180"]


class Registroc181(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c181"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c181"]


class Registroc185(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c185"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c185"]


class Registroc186(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c186"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c186"]


class Registroc190(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c190"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c190"]

    @api.model
    def _odoo_query(self, parent_record, declaration):
        # Analytical record: the document lines grouped by CST, CFOP and ICMS
        # rate. VL_OPR is the goods/operation value (ICMS world); CBS/IBS/IS are
        # excluded from the EFD amounts on layout 020.
        query = """
            SELECT
                CONCAT(COALESCE(line.icms_origin, '0'), cst.code) AS cst_icms,
                cfop.code AS cfop,
                line.icms_percent AS aliq_icms,
                SUM(line.price_gross) AS vl_opr,
                SUM(line.icms_base) AS vl_bc_icms,
                SUM(line.icms_value) AS vl_icms,
                SUM(line.icmsst_base) AS vl_bc_icms_st,
                SUM(line.icmsst_value) AS vl_icms_st,
                SUM(line.ipi_value) AS vl_ipi
            FROM l10n_br_fiscal_document_line line
            LEFT JOIN l10n_br_fiscal_cst cst ON cst.id = line.icms_cst_id
            LEFT JOIN l10n_br_fiscal_cfop cfop ON cfop.id = line.cfop_id
            WHERE line.document_id = %s
            GROUP BY cst.code, cfop.code, line.icms_percent, line.icms_origin
        """
        return query, [parent_record.id]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {
            "CST_ICMS": record.get("cst_icms") or "",
            "CFOP": record.get("cfop") or "",
            "ALIQ_ICMS": record.get("aliq_icms") or 0.0,
            "VL_OPR": record.get("vl_opr") or 0.0,
            "VL_BC_ICMS": record.get("vl_bc_icms") or 0.0,
            "VL_ICMS": record.get("vl_icms") or 0.0,
            "VL_BC_ICMS_ST": record.get("vl_bc_icms_st") or 0.0,
            "VL_ICMS_ST": record.get("vl_icms_st") or 0.0,
            "VL_RED_BC": 0.0,
            "VL_IPI": record.get("vl_ipi") or 0.0,
            "COD_OBS": "",
        }


class Registroc191(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c191"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c191"]


class Registroc195(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c195"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c195"]


class Registroc197(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c197"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c197"]


class Registroc300(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c300"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c300"]


class Registroc310(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c310"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c310"]


class Registroc320(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c320"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c320"]


class Registroc321(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c321"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c321"]


class Registroc330(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c330"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c330"]


class Registroc350(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c350"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c350"]


class Registroc370(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c370"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c370"]


class Registroc380(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c380"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c380"]


class Registroc390(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c390"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c390"]


class Registroc400(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c400"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c400"]


class Registroc405(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c405"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c405"]


class Registroc410(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c410"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c410"]


class Registroc420(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c420"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c420"]


class Registroc425(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c425"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c425"]


class Registroc430(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c430"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c430"]


class Registroc460(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c460"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c460"]


class Registroc465(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c465"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c465"]


class Registroc470(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c470"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c470"]


class Registroc480(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c480"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c480"]


class Registroc490(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c490"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c490"]


class Registroc495(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c495"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c495"]


class Registroc500(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c500"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c500"]
    _odoo_model = "l10n_br_fiscal.document"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        # Energy/water/gas utility documents acquired in the period.
        return [
            ("id", "in", declaration.fiscal_document_ids.ids),
            ("document_type_id.code", "in", UTILITY_MODELS),
        ]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {
            "IND_OPER": "0" if record.fiscal_operation_type == "in" else "1",
            "IND_EMIT": "0" if record.issuer == "company" else "1",
            "COD_PART": str(record.partner_id.id),
            "COD_MOD": record.document_type_id.code,
            "COD_SIT": record.state_fiscal,
            "SER": record.document_serie or "",
            "NUM_DOC": misc.punctuation_rm(str(record.document_number or "")),
            "DT_DOC": record.document_date,
            "DT_E_S": record.date_in_out,
            "VL_DOC": record.fiscal_amount_total,
            "VL_DESC": record.amount_discount_value,
            "VL_FORN": record.amount_price_gross,
            "VL_BC_ICMS": record.amount_icms_base,
            "VL_ICMS": record.amount_icms_value,
            "VL_BC_ICMS_ST": record.amount_icmsst_base,
            "VL_ICMS_ST": record.amount_icmsst_value,
            "VL_PIS": record.amount_pis_value,
            "VL_COFINS": record.amount_cofins_value,
        }


class Registroc510(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c510"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c510"]


class Registroc590(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c590"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c590"]

    @api.model
    def _odoo_query(self, parent_record, declaration):
        # Analytic record of the utility document, grouped by CST/CFOP/rate.
        query = """
            SELECT
                CONCAT(COALESCE(line.icms_origin, '0'), cst.code) AS cst_icms,
                cfop.code AS cfop,
                line.icms_percent AS aliq_icms,
                SUM(line.price_gross) AS vl_opr,
                SUM(line.icms_base) AS vl_bc_icms,
                SUM(line.icms_value) AS vl_icms,
                SUM(line.icmsst_base) AS vl_bc_icms_st,
                SUM(line.icmsst_value) AS vl_icms_st
            FROM l10n_br_fiscal_document_line line
            LEFT JOIN l10n_br_fiscal_cst cst ON cst.id = line.icms_cst_id
            LEFT JOIN l10n_br_fiscal_cfop cfop ON cfop.id = line.cfop_id
            WHERE line.document_id = %s
            GROUP BY cst.code, cfop.code, line.icms_percent, line.icms_origin
        """
        return query, [parent_record.id]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {
            "CST_ICMS": record.get("cst_icms") or "",
            "CFOP": record.get("cfop") or "",
            "ALIQ_ICMS": record.get("aliq_icms") or 0.0,
            "VL_OPR": record.get("vl_opr") or 0.0,
            "VL_BC_ICMS": record.get("vl_bc_icms") or 0.0,
            "VL_ICMS": record.get("vl_icms") or 0.0,
            "VL_BC_ICMS_ST": record.get("vl_bc_icms_st") or 0.0,
            "VL_ICMS_ST": record.get("vl_icms_st") or 0.0,
            "VL_RED_BC": 0.0,
            "COD_OBS": "",
        }


class Registroc591(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c591"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c591"]


class Registroc595(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c595"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c595"]


class Registroc597(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c597"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c597"]


class Registroc600(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c600"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c600"]


class Registroc601(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c601"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c601"]


class Registroc610(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c610"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c610"]


class Registroc690(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c690"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c690"]


class Registroc700(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c700"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c700"]


class Registroc790(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c790"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c790"]


class Registroc791(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c791"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c791"]


class Registroc800(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c800"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c800"]


class Registroc810(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c810"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c810"]


class Registroc815(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c815"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c815"]


class Registroc850(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c850"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c850"]


class Registroc855(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c855"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c855"]


class Registroc857(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c857"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c857"]


class Registroc860(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c860"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c860"]


class Registroc870(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c870"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c870"]


class Registroc880(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c880"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c880"]


class Registroc890(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c890"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c890"]


class Registroc895(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c895"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c895"]


class Registroc897(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.c897"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.c897"]


class Registrod100(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d100"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d100"]
    _odoo_model = "l10n_br_fiscal.document"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        # Transport documents (CT-e) received/issued in the period.
        return [
            ("id", "in", declaration.fiscal_document_ids.ids),
            ("document_type_id.code", "in", CTE_MODELS),
        ]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {
            "IND_OPER": "0" if record.fiscal_operation_type == "in" else "1",
            "IND_EMIT": "0" if record.issuer == "company" else "1",
            "COD_PART": str(record.partner_id.id),
            "COD_MOD": record.document_type_id.code,
            "COD_SIT": record.state_fiscal,
            "SER": record.document_serie or "",
            "NUM_DOC": misc.punctuation_rm(str(record.document_number or "")),
            "CHV_CTE": record.document_key or "",
            "DT_DOC": record.document_date,
            "DT_A_P": record.document_date,
            "VL_DOC": record.fiscal_amount_total,
            "VL_DESC": record.amount_discount_value,
            "IND_FRT": "9",
            "VL_SERV": record.amount_price_gross,
            "VL_BC_ICMS": record.amount_icms_base,
            "VL_ICMS": record.amount_icms_value,
            "VL_NT": 0.0,
            "COD_MUN_ORIG": record.partner_id.city_id.ibge_code or "",
            "COD_MUN_DEST": record.company_id.city_id.ibge_code or "",
        }


class Registrod110(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d110"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d110"]


class Registrod120(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d120"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d120"]


class Registrod130(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d130"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d130"]


class Registrod140(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d140"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d140"]


class Registrod150(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d150"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d150"]


class Registrod160(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d160"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d160"]


class Registrod161(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d161"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d161"]


class Registrod162(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d162"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d162"]


class Registrod170(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d170"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d170"]


class Registrod180(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d180"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d180"]


class Registrod190(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d190"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d190"]

    @api.model
    def _odoo_query(self, parent_record, declaration):
        # Analytic record of the transport document, grouped by CST/CFOP/rate.
        query = """
            SELECT
                CONCAT(COALESCE(line.icms_origin, '0'), cst.code) AS cst_icms,
                cfop.code AS cfop,
                line.icms_percent AS aliq_icms,
                SUM(line.price_gross) AS vl_opr,
                SUM(line.icms_base) AS vl_bc_icms,
                SUM(line.icms_value) AS vl_icms
            FROM l10n_br_fiscal_document_line line
            LEFT JOIN l10n_br_fiscal_cst cst ON cst.id = line.icms_cst_id
            LEFT JOIN l10n_br_fiscal_cfop cfop ON cfop.id = line.cfop_id
            WHERE line.document_id = %s
            GROUP BY cst.code, cfop.code, line.icms_percent, line.icms_origin
        """
        return query, [parent_record.id]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {
            "CST_ICMS": record.get("cst_icms") or "",
            "CFOP": record.get("cfop") or "",
            "ALIQ_ICMS": record.get("aliq_icms") or 0.0,
            "VL_OPR": record.get("vl_opr") or 0.0,
            "VL_BC_ICMS": record.get("vl_bc_icms") or 0.0,
            "VL_ICMS": record.get("vl_icms") or 0.0,
            "VL_RED_BC": 0.0,
            "COD_OBS": "",
        }


class Registrod195(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d195"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d195"]


class Registrod197(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d197"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d197"]


class Registrod300(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d300"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d300"]


class Registrod301(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d301"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d301"]


class Registrod310(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d310"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d310"]


class Registrod350(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d350"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d350"]


class Registrod355(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d355"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d355"]


class Registrod360(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d360"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d360"]


class Registrod365(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d365"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d365"]


class Registrod370(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d370"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d370"]


class Registrod390(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d390"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d390"]


class Registrod400(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d400"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d400"]


class Registrod410(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d410"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d410"]


class Registrod411(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d411"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d411"]


class Registrod420(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d420"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d420"]


class Registrod500(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d500"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d500"]


class Registrod510(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d510"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d510"]


class Registrod530(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d530"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d530"]


class Registrod590(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d590"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d590"]


class Registrod600(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d600"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d600"]


class Registrod610(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d610"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d610"]


class Registrod690(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d690"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d690"]


class Registrod695(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d695"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d695"]


class Registrod696(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d696"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d696"]


class Registrod697(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d697"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d697"]


class Registrod700(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d700"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d700"]


class Registrod730(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d730"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d730"]


class Registrod731(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d731"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d731"]


class Registrod735(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d735"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d735"]


class Registrod737(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d737"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d737"]


class Registrod750(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d750"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d750"]


class Registrod760(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d760"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d760"]


class Registrod761(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.d761"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.d761"]


class Registroe100(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e100"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e100"]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        # ICMS assessment period: one record per declaration period.
        return {"DT_INI": declaration.DT_INI, "DT_FIN": declaration.DT_FIN}


class Registroe110(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e110"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e110"]

    @api.model
    def _odoo_query(self, parent_record, declaration):
        # ICMS assessment: debits from outgoing documents, credits from incoming
        # ones, over the period. Adjustments (E111/E116) and prior balances are
        # entered manually.
        query = """
            SELECT
                COALESCE(SUM(line.icms_value)
                    FILTER (WHERE doc.fiscal_operation_type = 'out'), 0) AS vl_debitos,
                COALESCE(SUM(line.icms_value)
                    FILTER (WHERE doc.fiscal_operation_type = 'in'), 0) AS vl_creditos
            FROM l10n_br_fiscal_document_line line
            JOIN l10n_br_fiscal_document doc ON doc.id = line.document_id
            WHERE doc.company_id = %s
              AND doc.document_date >= %s
              AND doc.document_date <= %s
              AND doc.state_edoc = 'autorizada'
        """
        params = [declaration.company_id.id, declaration.DT_INI, declaration.DT_FIN]
        return query, params

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        debits = record.get("vl_debitos") or 0.0
        credits = record.get("vl_creditos") or 0.0
        balance = debits - credits
        return {
            "VL_TOT_DEBITOS": debits,
            "VL_AJ_DEBITOS": 0.0,
            "VL_TOT_AJ_DEBITOS": 0.0,
            "VL_ESTORNOS_CRED": 0.0,
            "VL_TOT_CREDITOS": credits,
            "VL_AJ_CREDITOS": 0.0,
            "VL_TOT_AJ_CREDITOS": 0.0,
            "VL_ESTORNOS_DEB": 0.0,
            "VL_SLD_CREDOR_ANT": 0.0,
            "VL_SLD_APURADO": balance if balance > 0 else 0.0,
            "VL_TOT_DED": 0.0,
            "VL_ICMS_RECOLHER": balance if balance > 0 else 0.0,
            "VL_SLD_CREDOR_TRANSPORTAR": -balance if balance < 0 else 0.0,
            "DEB_ESP": 0.0,
        }


class Registroe111(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e111"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e111"]


class Registroe112(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e112"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e112"]


class Registroe113(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e113"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e113"]


class Registroe115(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e115"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e115"]


class Registroe116(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e116"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e116"]


class Registroe200(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e200"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e200"]


class Registroe210(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e210"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e210"]


class Registroe230(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e230"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e230"]


class Registroe240(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e240"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e240"]


class Registroe250(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e250"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e250"]


class Registroe300(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e300"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e300"]


class Registroe310(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e310"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e310"]


class Registroe311(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e311"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e311"]


class Registroe312(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e312"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e312"]


class Registroe313(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e313"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e313"]


class Registroe316(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e316"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e316"]


class Registroe500(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e500"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e500"]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        # IPI assessment period: one record per declaration period.
        return {
            "IND_APUR": declaration.ind_apur,
            "DT_INI": declaration.DT_INI,
            "DT_FIN": declaration.DT_FIN,
        }


class Registroe510(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e510"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e510"]


class Registroe520(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e520"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e520"]

    @api.model
    def _odoo_query(self, parent_record, declaration):
        # IPI assessment: debits from outgoing documents, credits from incoming
        # ones, over the period. Prior balance and other adjustments are manual.
        query = """
            SELECT
                COALESCE(SUM(line.ipi_value)
                    FILTER (WHERE doc.fiscal_operation_type = 'out'), 0) AS vl_deb,
                COALESCE(SUM(line.ipi_value)
                    FILTER (WHERE doc.fiscal_operation_type = 'in'), 0) AS vl_cred
            FROM l10n_br_fiscal_document_line line
            JOIN l10n_br_fiscal_document doc ON doc.id = line.document_id
            WHERE doc.company_id = %s
              AND doc.document_date >= %s
              AND doc.document_date <= %s
              AND doc.state_edoc = 'autorizada'
        """
        params = [declaration.company_id.id, declaration.DT_INI, declaration.DT_FIN]
        return query, params

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        debits = record.get("vl_deb") or 0.0
        credits = record.get("vl_cred") or 0.0
        balance = debits - credits
        return {
            "VL_SD_ANT_IPI": 0.0,
            "VL_DEB_IPI": debits,
            "VL_CRED_IPI": credits,
            "VL_OD_IPI": 0.0,
            "VL_OC_IPI": 0.0,
            "VL_SC_IPI": -balance if balance < 0 else 0.0,
            "VL_SD_IPI": balance if balance > 0 else 0.0,
        }


class Registroe530(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e530"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e530"]


class Registroe531(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.e531"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.e531"]


class Registrog110(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.g110"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.g110"]


class Registrog126(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.g126"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.g126"]


class Registrog130(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.g130"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.g130"]


class Registrog140(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.g140"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.g140"]


class Registroh005(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.h005"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.h005"]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        # Period-end inventory totals (one record per declaration).
        products = (
            self.env["product.product"]
            .with_context(to_date=declaration.DT_FIN)
            .search([("is_storable", "=", True)])
        )
        vl_inv = sum(p.qty_available * p.standard_price for p in products)
        return {
            "DT_INV": declaration.DT_FIN,
            "VL_INV": vl_inv,
            "MOT_INV": "01",
        }


class Registroh010(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.h010"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.h010"]
    _odoo_model = "product.product"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        return [("is_storable", "=", True)]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        product = record.with_context(to_date=declaration.DT_FIN)
        qty = product.qty_available or 0.0
        # standard_price is the current cost, not the historical one at DT_FIN.
        vl_unit = record.standard_price or 0.0
        vl_item = qty * vl_unit
        return {
            "COD_ITEM": record.default_code or str(record.id),
            "UNID": record.uom_id.code or record.uom_id.name,
            "QTD": qty,
            "VL_UNIT": vl_unit,
            "VL_ITEM": vl_item,
            "IND_PROP": "0",
            "COD_PART": "",
            "TXT_COMPL": "",
            "COD_CTA": "",
            "VL_ITEM_IR": vl_item,
        }


class Registroh020(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.h020"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.h020"]


class Registroh030(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.h030"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.h030"]


class Registrok010(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k010"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k010"]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {"IND_TP_LEIAUTE": declaration.ind_tp_leiaute}


class Registrok100(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k100"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k100"]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        # Stock/production assessment period: one record per declaration period.
        return {"DT_INI": declaration.DT_INI, "DT_FIN": declaration.DT_FIN}


class Registrok200(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k200"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k200"]
    _odoo_model = "product.product"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        return [("is_storable", "=", True)]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        # End-of-period stock balance (historical quantity at DT_FIN).
        qty = record.with_context(
            to_date=declaration.DT_FIN, company_id=declaration.company_id.id
        ).qty_available
        return {
            "DT_EST": declaration.DT_FIN,
            "COD_ITEM": record.default_code or str(record.id),
            "QTD": qty,
            "IND_EST": "0",
            "COD_PART": "",
        }


class Registrok210(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k210"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k210"]


class Registrok215(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k215"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k215"]


class Registrok220(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k220"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k220"]


class Registrok230(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k230"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k230"]

    @api.model
    def _odoo_query(self, parent_record, declaration):
        # Production orders finished in the period. mrp is a soft dependency:
        # the data is read by SQL and yields nothing when mrp is not installed,
        # so the base module stays installable without manufacturing.
        if "mrp.production" not in self.env:
            return "SELECT NULL AS id WHERE FALSE", []
        query = """
            SELECT
                mo.id AS id,
                mo.name AS cod_doc_op,
                mo.date_start AS dt_ini_op,
                mo.date_finished AS dt_fin_op,
                COALESCE(NULLIF(mo.qty_producing, 0), mo.product_qty) AS qtd_enc,
                COALESCE(pp.default_code, mo.product_id::text) AS cod_item
            FROM mrp_production mo
            JOIN product_product pp ON pp.id = mo.product_id
            WHERE mo.state = 'done'
              AND mo.company_id = %s
              AND mo.date_finished >= %s
              AND mo.date_finished <= %s
        """
        return query, [
            declaration.company_id.id,
            declaration.DT_INI,
            declaration.DT_FIN,
        ]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {
            "DT_INI_OP": record.get("dt_ini_op"),
            "DT_FIN_OP": record.get("dt_fin_op"),
            "COD_DOC_OP": record.get("cod_doc_op") or "",
            "COD_ITEM": record.get("cod_item") or "",
            "QTD_ENC": record.get("qtd_enc") or 0.0,
        }


class Registrok235(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k235"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k235"]

    @api.model
    def _odoo_query(self, parent_record, declaration):
        # Raw materials consumed by the parent production order (K230 row).
        if "mrp.production" not in self.env or not parent_record:
            return "SELECT NULL AS id WHERE FALSE", []
        query = """
            SELECT
                sm.date AS dt_saida,
                sm.quantity AS qtd,
                COALESCE(pp.default_code, sm.product_id::text) AS cod_item
            FROM stock_move sm
            JOIN product_product pp ON pp.id = sm.product_id
            WHERE sm.raw_material_production_id = %s
              AND sm.state = 'done'
        """
        return query, [parent_record["id"]]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {
            "DT_SAIDA": record.get("dt_saida"),
            "COD_ITEM": record.get("cod_item") or "",
            "QTD": record.get("qtd") or 0.0,
            "COD_INS_SUBST": "",
        }


class Registrok250(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k250"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k250"]


class Registrok255(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k255"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k255"]


class Registrok260(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k260"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k260"]


class Registrok265(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k265"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k265"]


class Registrok270(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k270"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k270"]


class Registrok275(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k275"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k275"]


class Registrok280(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k280"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k280"]


class Registrok290(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k290"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k290"]


class Registrok291(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k291"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k291"]


class Registrok292(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k292"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k292"]


class Registrok301(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k301"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k301"]


class Registrok302(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.k302"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.k302"]


class Registro1010(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1010"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1010"]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        # Obligation indicators for the 1xxx sub-blocks. Defaults to "N" (none);
        # the user enables the specific ones that apply to the establishment.
        return {
            "IND_EXP": "N",
            "IND_CCRF": "N",
            "IND_COMB": "N",
            "IND_USINA": "N",
            "IND_VA": "N",
            "IND_EE": "N",
            "IND_CART": "N",
            "IND_FORM": "N",
            "IND_AER": "N",
            "IND_REST_RESSARC_COMPL_ICMS": "N",
        }


class Registro1100(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1100"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1100"]


class Registro1105(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1105"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1105"]


class Registro1110(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1110"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1110"]


class Registro1200(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1200"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1200"]


class Registro1210(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1210"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1210"]


class Registro1250(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1250"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1250"]


class Registro1255(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1255"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1255"]


class Registro1300(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1300"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1300"]


class Registro1310(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1310"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1310"]


class Registro1320(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1320"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1320"]


class Registro1350(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1350"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1350"]


class Registro1360(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1360"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1360"]


class Registro1370(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1370"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1370"]


class Registro1390(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1390"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1390"]


class Registro1391(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1391"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1391"]


class Registro1400(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1400"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1400"]


class Registro1500(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1500"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1500"]


class Registro1510(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1510"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1510"]


class Registro1600(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1600"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1600"]


class Registro1601(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1601"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1601"]


class Registro1700(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1700"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1700"]


class Registro1710(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1710"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1710"]


class Registro1800(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1800"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1800"]


class Registro1900(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1900"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1900"]


class Registro1910(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1910"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1910"]


class Registro1920(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1920"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1920"]


class Registro1921(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1921"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1921"]


class Registro1922(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1922"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1922"]


class Registro1923(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1923"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1923"]


class Registro1925(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1925"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1925"]


class Registro1926(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1926"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1926"]


class Registro1960(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1960"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1960"]


class Registro1970(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1970"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1970"]


class Registro1975(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1975"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1975"]


class Registro1980(models.Model):
    _name = "l10n_br_sped.efd_icms_ipi.1980"
    _inherit = ["l10n_br_sped.efd_icms_ipi.20.1980"]
