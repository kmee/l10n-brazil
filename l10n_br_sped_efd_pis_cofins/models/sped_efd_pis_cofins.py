# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
#
# Concrete EFD Contribuições (PIS/COFINS) registers and their mappings from
# Odoo transactions. Each concrete register inherits its generated abstract
# spec from sped_efd_pis_cofins_spec_6.py and implements the mapping hooks of
# l10n_br_sped.mixin. New blocks are added here phase by phase.

import textwrap

from erpbrasil.base import misc

from odoo import api, fields, models

LAYOUT_VERSION_CODE = "006"

# Fiscal document model codes routed to other blocks (kept out of Bloco C).
CTE_MODELS = ["57", "67"]  # transport
UTILITY_MODELS = ["06", "28", "29", "66"]  # energy/water/gas

_PERIOD_WHERE = (
    "doc.company_id = %s AND doc.document_date >= %s "
    "AND doc.document_date <= %s AND doc.state_edoc = 'autorizada'"
)


def _contrib_params(declaration):
    return [declaration.company_id.id, declaration.DT_INI, declaration.DT_FIN]


def _consolidation_query(value_col):
    """Period debit (sales) and credit (purchases) of a PIS/COFINS value column.

    Baseline assessment: the precise PIS/COFINS rules are CST-driven; the
    accountant refines per-CST. value_col is a fixed identifier, not user input.
    """
    return f"""
        SELECT
            COALESCE(SUM(line.{value_col})
                FILTER (WHERE doc.fiscal_operation_type = 'out'), 0) AS deb,
            COALESCE(SUM(line.{value_col})
                FILTER (WHERE doc.fiscal_operation_type = 'in'), 0) AS cred
        FROM l10n_br_fiscal_document_line line
        JOIN l10n_br_fiscal_document doc ON doc.id = line.document_id
        WHERE {_PERIOD_WHERE}
    """


def _contrib_detail_query(base_col, aliq_col, value_col, direction):
    """Aggregate a PIS/COFINS contribution by rate for one operation direction."""
    return f"""
        SELECT
            line.{aliq_col} AS aliq,
            SUM(line.{base_col}) AS vl_bc,
            SUM(line.{value_col}) AS vl_cont
        FROM l10n_br_fiscal_document_line line
        JOIN l10n_br_fiscal_document doc ON doc.id = line.document_id
        WHERE {_PERIOD_WHERE} AND doc.fiscal_operation_type = '{direction}'
        GROUP BY line.{aliq_col}
    """


class Registro0000(models.Model):
    "Abertura do Arquivo Digital e Identificação da Pessoa Jurídica"

    _description = textwrap.dedent(f"    {__doc__}")
    _name = "l10n_br_sped.efd_pis_cofins.0000"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0000"]
    _odoo_model = "res.company"

    COD_VER = fields.Char(default=LAYOUT_VERSION_CODE)

    TIPO_ESCRIT = fields.Selection(
        selection=[
            ("0", "0 - Escrituração original"),
            ("1", "1 - Escrituração retificadora"),
        ],
        string="Tipo de escrituração",
        default="0",
    )

    IND_NAT_PJ = fields.Selection(
        selection=[
            ("00", "00 - Sociedade empresária em geral"),
            ("01", "01 - Sociedade cooperativa"),
            ("02", "02 - Entidade sujeita ao PIS/Pasep por folha de salários"),
        ],
        string="Indicador da natureza da pessoa jurídica",
        default="00",
    )

    IND_ATIV = fields.Selection(
        selection=[
            ("0", "0 - Industrial ou equiparado a industrial"),
            ("1", "1 - Prestador de serviços"),
            ("2", "2 - Atividade de comércio"),
            ("3", "3 - Pessoas jurídicas do art. 10 da Lei 10.833/2003"),
            ("4", "4 - Atividade imobiliária"),
            ("9", "9 - Outros"),
        ],
        string="Indicador de tipo de atividade preponderante",
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
            "TIPO_ESCRIT": "0",
            "NOME": record.legal_name or record.name,
            "CNPJ": misc.punctuation_rm(record.vat or ""),
            "UF": record.state_id.code or "",
            "COD_MUN": record.city_id.ibge_code or "",
            "SUFRAMA": record.l10n_br_isuf_code or "",
            "IND_NAT_PJ": "00",
            "IND_ATIV": "0",
        }

    @api.model_create_multi
    def create(self, vals_list):
        # Fill the mandatory 0000 fields (NOME, CNPJ, UF...) from the company at
        # creation, so the declaration is valid without relying on the form
        # onchange (which does not fire on programmatic/headless create).
        for vals in vals_list:
            company = (
                self.env["res.company"].browse(vals.get("company_id"))
                or self.env.company
            )
            if company and not vals.get("NOME"):
                for key, value in self._map_from_odoo(company, None, self).items():
                    vals.setdefault(key, value)
        return super().create(vals_list)

    def button_populate_sped_from_odoo(self):
        # Re-sync the 0000 fields from the company before pulling the children.
        for declaration in self:
            if declaration.company_id:
                declaration.write(
                    declaration._map_from_odoo(
                        declaration.company_id, None, declaration
                    )
                )
        return super().button_populate_sped_from_odoo()


# -------------------------------------------------------------------------
# Concrete register stubs (one per spec register so the inter-register
# relations resolve). Mappings are added block by block.
# -------------------------------------------------------------------------


class Registro0035(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0035"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0035"]


class Registro0100(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0100"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0100"]


class Registro0110(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0110"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0110"]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        # Assessment regime (one record per declaration). Defaults to the most
        # common case (non-cumulative, e.g. Lucro Real); adjust per company.
        return {
            "COD_INC_TRIB": "1",
            "IND_APRO_CRED": "1",
            "COD_TIPO_CONT": "0",
        }


class Registro0111(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0111"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0111"]


class Registro0120(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0120"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0120"]


class Registro0140(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0140"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0140"]
    _odoo_model = "res.company"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        return [("id", "=", declaration.company_id.id)]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {
            "COD_EST": str(record.id),
            "NOME": record.legal_name or record.name,
            "CNPJ": misc.punctuation_rm(record.vat or ""),
            "UF": record.state_id.code or "",
            "IE": record.l10n_br_ie_code or "",
            "COD_MUN": record.city_id.ibge_code or "",
            "IM": record.l10n_br_im_code or "",
            "SUFRAMA": record.l10n_br_isuf_code or "",
        }


class Registro0145(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0145"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0145"]


class Registro0150(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0150"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0150"]
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


class Registro0190(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0190"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0190"]
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
    _name = "l10n_br_sped.efd_pis_cofins.0200"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0200"]
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
        }


class Registro0205(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0205"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0205"]


class Registro0206(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0206"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0206"]


class Registro0208(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0208"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0208"]


class Registro0400(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0400"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0400"]


class Registro0450(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0450"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0450"]


class Registro0500(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0500"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0500"]


class Registro0600(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0600"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0600"]


class Registro0900(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.0900"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.0900"]


class Registroa010(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.a010"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.a010"]


class Registroa100(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.a100"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.a100"]


class Registroa110(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.a110"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.a110"]


class Registroa111(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.a111"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.a111"]


class Registroa120(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.a120"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.a120"]


class Registroa170(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.a170"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.a170"]


class Registroc010(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c010"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c010"]
    _odoo_model = "res.company"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        return [("id", "=", declaration.company_id.id)]

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        return {
            "CNPJ": misc.punctuation_rm(record.vat or ""),
            "IND_ESCRI": "1",
        }


class Registroc100(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c100"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c100"]
    _odoo_model = "l10n_br_fiscal.document"

    @api.model
    def _odoo_domain(self, parent_record, declaration):
        return [
            ("id", "in", declaration.fiscal_document_ids.ids),
            ("document_type_id.code", "not in", CTE_MODELS + UTILITY_MODELS),
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


class Registroc110(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c110"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c110"]


class Registroc111(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c111"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c111"]


class Registroc120(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c120"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c120"]


class Registroc170(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c170"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c170"]

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
            "IND_APUR": "0",
            "CST_IPI": record.ipi_cst_code or "",
            "COD_ENQ": record.ipi_guideline_id.code or "",
            "VL_BC_IPI": record.ipi_base,
            "ALIQ_IPI": record.ipi_percent,
            "VL_IPI": record.ipi_value,
            "CST_PIS": record.pis_cst_code or "",
            "VL_BC_PIS": record.pis_base,
            "ALIQ_PIS": record.pis_percent,
            "QUANT_BC_PIS": 0.0,
            "ALIQ_PIS_QUANT": 0.0,
            "VL_PIS": record.pis_value,
            "CST_COFINS": record.cofins_cst_code or "",
            "VL_BC_COFINS": record.cofins_base,
            "ALIQ_COFINS": record.cofins_percent,
            "QUANT_BC_COFINS": 0.0,
            "ALIQ_COFINS_QUANT": 0.0,
            "VL_COFINS": record.cofins_value,
            "COD_CTA": "",
        }


class Registroc175(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c175"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c175"]


class Registroc180(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c180"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c180"]


class Registroc181(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c181"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c181"]


class Registroc185(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c185"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c185"]


class Registroc188(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c188"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c188"]


class Registroc190(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c190"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c190"]


class Registroc191(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c191"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c191"]


class Registroc195(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c195"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c195"]


class Registroc198(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c198"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c198"]


class Registroc199(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c199"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c199"]


class Registroc380(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c380"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c380"]


class Registroc381(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c381"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c381"]


class Registroc385(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c385"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c385"]


class Registroc395(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c395"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c395"]


class Registroc396(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c396"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c396"]


class Registroc400(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c400"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c400"]


class Registroc405(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c405"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c405"]


class Registroc481(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c481"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c481"]


class Registroc485(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c485"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c485"]


class Registroc489(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c489"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c489"]


class Registroc490(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c490"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c490"]


class Registroc491(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c491"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c491"]


class Registroc495(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c495"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c495"]


class Registroc499(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c499"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c499"]


class Registroc500(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c500"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c500"]


class Registroc501(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c501"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c501"]


class Registroc505(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c505"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c505"]


class Registroc509(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c509"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c509"]


class Registroc600(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c600"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c600"]


class Registroc601(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c601"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c601"]


class Registroc605(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c605"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c605"]


class Registroc609(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c609"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c609"]


class Registroc800(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c800"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c800"]


class Registroc810(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c810"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c810"]


class Registroc820(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c820"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c820"]


class Registroc830(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c830"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c830"]


class Registroc860(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c860"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c860"]


class Registroc870(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c870"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c870"]


class Registroc880(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c880"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c880"]


class Registroc890(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.c890"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.c890"]


class Registrod010(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d010"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d010"]


class Registrod100(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d100"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d100"]


class Registrod101(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d101"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d101"]


class Registrod105(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d105"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d105"]


class Registrod111(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d111"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d111"]


class Registrod200(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d200"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d200"]


class Registrod201(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d201"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d201"]


class Registrod205(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d205"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d205"]


class Registrod209(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d209"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d209"]


class Registrod300(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d300"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d300"]


class Registrod309(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d309"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d309"]


class Registrod350(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d350"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d350"]


class Registrod359(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d359"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d359"]


class Registrod500(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d500"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d500"]


class Registrod501(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d501"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d501"]


class Registrod505(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d505"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d505"]


class Registrod509(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d509"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d509"]


class Registrod600(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d600"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d600"]


class Registrod601(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d601"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d601"]


class Registrod605(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d605"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d605"]


class Registrod609(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.d609"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.d609"]


class Registrof010(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f010"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f010"]


class Registrof100(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f100"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f100"]


class Registrof111(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f111"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f111"]


class Registrof120(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f120"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f120"]


class Registrof129(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f129"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f129"]


class Registrof130(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f130"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f130"]


class Registrof139(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f139"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f139"]


class Registrof150(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f150"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f150"]


class Registrof200(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f200"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f200"]


class Registrof205(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f205"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f205"]


class Registrof210(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f210"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f210"]


class Registrof211(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f211"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f211"]


class Registrof500(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f500"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f500"]


class Registrof509(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f509"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f509"]


class Registrof510(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f510"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f510"]


class Registrof519(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f519"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f519"]


class Registrof525(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f525"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f525"]


class Registrof550(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f550"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f550"]


class Registrof559(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f559"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f559"]


class Registrof560(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f560"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f560"]


class Registrof569(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f569"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f569"]


class Registrof600(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f600"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f600"]


class Registrof700(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f700"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f700"]


class Registrof800(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.f800"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.f800"]


class Registroi010(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.i010"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.i010"]


class Registroi100(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.i100"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.i100"]


class Registroi199(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.i199"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.i199"]


class Registroi200(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.i200"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.i200"]


class Registroi299(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.i299"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.i299"]


class Registroi300(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.i300"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.i300"]


class Registroi399(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.i399"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.i399"]


class Registrom100(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m100"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m100"]

    @api.model
    def _odoo_query(self, parent_record, declaration):
        query = _contrib_detail_query("pis_base", "pis_percent", "pis_value", "in")
        return query, _contrib_params(declaration)

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        bc = record.get("vl_bc") or 0.0
        cred = record.get("vl_cont") or 0.0
        return {
            "COD_CRED": "101",
            "IND_CRED_ORI": "0",
            "VL_BC_PIS": bc,
            "ALIQ_PIS": record.get("aliq") or 0.0,
            "QUANT_BC_PIS": 0.0,
            "ALIQ_PIS_QUANT": 0.0,
            "VL_CRED": cred,
            "VL_AJUS_ACRES": 0.0,
            "VL_AJUS_REDUC": 0.0,
            "VL_CRED_DIF": 0.0,
            "VL_CRED_DISP": cred,
            "IND_DESC_CRED": "0",
            "VL_CRED_DESC": cred,
            "SLD_CRED": 0.0,
        }


class Registrom105(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m105"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m105"]


class Registrom110(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m110"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m110"]


class Registrom115(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m115"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m115"]


class Registrom200(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m200"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m200"]

    @api.model
    def _odoo_query(self, parent_record, declaration):
        return _consolidation_query("pis_value"), _contrib_params(declaration)

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        deb = record.get("deb") or 0.0
        cred = record.get("cred") or 0.0
        rec = max(deb - cred, 0.0)
        return {
            "VL_TOT_CONT_NC_PER": deb,
            "VL_TOT_CRED_DESC": cred,
            "VL_TOT_CRED_DESC_ANT": 0.0,
            "VL_TOT_CONT_NC_DEV": rec,
            "VL_RET_NC": 0.0,
            "VL_OUT_DED_NC": 0.0,
            "VL_CONT_NC_REC": rec,
            "VL_TOT_CONT_CUM_PER": 0.0,
            "VL_RET_CUM": 0.0,
            "VL_OUT_DED_CUM": 0.0,
            "VL_CONT_CUM_REC": 0.0,
            "VL_TOT_CONT_REC": rec,
        }


class Registrom205(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m205"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m205"]


class Registrom210(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m210"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m210"]

    @api.model
    def _odoo_query(self, parent_record, declaration):
        query = _contrib_detail_query("pis_base", "pis_percent", "pis_value", "out")
        return query, _contrib_params(declaration)

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        bc = record.get("vl_bc") or 0.0
        cont = record.get("vl_cont") or 0.0
        return {
            "COD_CONT": "01",
            "VL_REC_BRT": bc,
            "VL_BC_CONT": bc,
            "ALIQ_PIS": record.get("aliq") or 0.0,
            "QUANT_BC_PIS": 0.0,
            "ALIQ_PIS_QUANT": 0.0,
            "VL_CONT_APUR": cont,
            "VL_AJUS_ACRES": 0.0,
            "VL_AJUS_REDUC": 0.0,
            "VL_CONT_DIFER": 0.0,
            "VL_CONT_DIFER_ANT": 0.0,
            "VL_CONT_PER": cont,
        }


class Registrom211(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m211"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m211"]


class Registrom215(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m215"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m215"]


class Registrom220(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m220"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m220"]


class Registrom225(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m225"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m225"]


class Registrom230(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m230"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m230"]


class Registrom300(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m300"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m300"]


class Registrom350(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m350"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m350"]


class Registrom400(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m400"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m400"]


class Registrom410(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m410"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m410"]


class Registrom500(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m500"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m500"]

    @api.model
    def _odoo_query(self, parent_record, declaration):
        query = _contrib_detail_query(
            "cofins_base", "cofins_percent", "cofins_value", "in"
        )
        return query, _contrib_params(declaration)

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        bc = record.get("vl_bc") or 0.0
        cred = record.get("vl_cont") or 0.0
        return {
            "COD_CRED": "101",
            "IND_CRED_ORI": "0",
            "VL_BC_COFINS": bc,
            "ALIQ_COFINS": record.get("aliq") or 0.0,
            "QUANT_BC_COFINS": 0.0,
            "ALIQ_COFINS_QUANT": 0.0,
            "VL_CRED": cred,
            "VL_AJUS_ACRES": 0.0,
            "VL_AJUS_REDUC": 0.0,
            "VL_CRED_DIFER": 0.0,
            "VL_CRED_DISP": cred,
            "IND_DESC_CRED": "0",
            "VL_CRED_DESC": cred,
            "SLD_CRED": 0.0,
        }


class Registrom505(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m505"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m505"]


class Registrom510(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m510"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m510"]


class Registrom515(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m515"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m515"]


class Registrom600(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m600"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m600"]

    @api.model
    def _odoo_query(self, parent_record, declaration):
        return _consolidation_query("cofins_value"), _contrib_params(declaration)

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        deb = record.get("deb") or 0.0
        cred = record.get("cred") or 0.0
        rec = max(deb - cred, 0.0)
        return {
            "VL_TOT_CONT_NC_PER": deb,
            "VL_TOT_CRED_DESC": cred,
            "VL_TOT_CRED_DESC_ANT": 0.0,
            "VL_TOT_CONT_NC_DEV": rec,
            "VL_RET_NC": 0.0,
            "VL_OUT_DED_NC": 0.0,
            "VL_CONT_NC_REC": rec,
            "VL_TOT_CONT_CUM_PER": 0.0,
            "VL_RET_CUM": 0.0,
            "VL_OUT_DED_CUM": 0.0,
            "VL_CONT_CUM_REC": 0.0,
            "VL_TOT_CONT_REC": rec,
        }


class Registrom605(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m605"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m605"]


class Registrom610(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m610"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m610"]

    @api.model
    def _odoo_query(self, parent_record, declaration):
        query = _contrib_detail_query(
            "cofins_base", "cofins_percent", "cofins_value", "out"
        )
        return query, _contrib_params(declaration)

    @api.model
    def _map_from_odoo(self, record, parent_record, declaration, index=0):
        bc = record.get("vl_bc") or 0.0
        cont = record.get("vl_cont") or 0.0
        return {
            "COD_CONT": "01",
            "VL_REC_BRT": bc,
            "VL_BC_CONT": bc,
            "ALIQ_COFINS": record.get("aliq") or 0.0,
            "QUANT_BC_COFINS": 0.0,
            "ALIQ_COFINS_QUANT": 0.0,
            "VL_CONT_APUR": cont,
            "VL_AJUS_ACRES": 0.0,
            "VL_AJUS_REDUC": 0.0,
            "VL_CONT_DIFER": 0.0,
            "VL_CONT_DIFER_ANT": 0.0,
            "VL_CONT_PER": cont,
        }


class Registrom611(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m611"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m611"]


class Registrom615(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m615"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m615"]


class Registrom620(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m620"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m620"]


class Registrom625(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m625"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m625"]


class Registrom630(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m630"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m630"]


class Registrom700(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m700"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m700"]


class Registrom800(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m800"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m800"]


class Registrom810(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.m810"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.m810"]


class Registrop010(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.p010"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.p010"]


class Registrop100(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.p100"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.p100"]


class Registrop110(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.p110"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.p110"]


class Registrop199(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.p199"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.p199"]


class Registrop200(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.p200"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.p200"]


class Registrop210(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.p210"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.p210"]


class Registro1010(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1010"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1010"]


class Registro1011(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1011"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1011"]


class Registro1020(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1020"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1020"]


class Registro1050(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1050"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1050"]


class Registro1100(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1100"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1100"]


class Registro1101(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1101"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1101"]


class Registro1102(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1102"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1102"]


class Registro1200(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1200"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1200"]


class Registro1210(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1210"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1210"]


class Registro1220(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1220"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1220"]


class Registro1300(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1300"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1300"]


class Registro1500(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1500"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1500"]


class Registro1501(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1501"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1501"]


class Registro1502(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1502"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1502"]


class Registro1600(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1600"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1600"]


class Registro1610(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1610"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1610"]


class Registro1620(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1620"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1620"]


class Registro1700(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1700"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1700"]


class Registro1800(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1800"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1800"]


class Registro1809(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1809"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1809"]


class Registro1900(models.Model):
    _name = "l10n_br_sped.efd_pis_cofins.1900"
    _inherit = ["l10n_br_sped.efd_pis_cofins.6.1900"]
