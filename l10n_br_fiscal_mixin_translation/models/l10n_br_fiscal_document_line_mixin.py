# Copyright 2020 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _


class L10n_br_fiscalDocumentLineMixin(models.Model):

    _inherit = 'l10n_br_fiscal.document.line.mixin'

    currency_id = fields.Many2one(
        string="Currency",
    )

    product_id = fields.Many2one(
        string="Product"
    )

    tax_icms_or_issqn = fields.Selection(
        string='ICMS or ISSQN Tax',
    )

    price_unit = fields.Float(
        string="Price Unit",
    )

    partner_id = fields.Many2one(
        string="Partner")

    partner_company_type = fields.Selection(
        string='Company Type',
    )

    uom_id = fields.Many2one(
        string="UOM"
    )

    quantity = fields.Float(
        string="Quantity",
    )

    fiscal_type = fields.Selection(
        string="Fiscal Type")

    ncm_id = fields.Many2one(
        string="NCM")

    nbm_id = fields.Many2one(
        string="NBM",
    )

    cest_id = fields.Many2one(
        string="CEST",
    )

    nbs_id = fields.Many2one(
        string="NBS")

    fiscal_operation_id = fields.Many2one(
        string="Operation",
    )

    fiscal_operation_type = fields.Selection(
        string="Fiscal Operation Type"
    )

    fiscal_operation_line_id = fields.Many2one(
        string="Operation Line",
    )

    cfop_id = fields.Many2one(
        string="CFOP",
    )

    cfop_destination = fields.Selection(
        string="CFOP Destination"
    )

    fiscal_price = fields.Float(
        string="Fiscal Price",
    )

    uot_id = fields.Many2one(
        string="Tax UoM")

    fiscal_quantity = fields.Float(
        string="Fiscal Quantity",
    )

    discount_value = fields.Monetary(
        string="Discount Value",
    )

    insurance_value = fields.Monetary(
        string='Insurance Value',
    )

    other_costs_value = fields.Monetary(
        string='Other Costs',
    )

    freight_value = fields.Monetary(
        string='Freight Value',
    )

    fiscal_tax_ids = fields.Many2many(
        string="Fiscal Taxes"
    )

    amount_tax_not_included = fields.Monetary(
        string="Amount Tax not Included",
    )

    amount_tax_withholding = fields.Monetary(
        string="Amount Tax Withholding",
    )

    fiscal_genre_id = fields.Many2one(
        string="Fiscal Product Genre")

    fiscal_genre_code = fields.Char(
        string="Fiscal Product Genre Code"
    )

    service_type_id = fields.Many2one(
        string="Service Type LC 166",
    )

    partner_order = fields.Char(
        string='Partner Order (xPed)',
    )

    partner_order_line = fields.Char(
        string='Partner Order Line (nItemPed)',
    )

    # ISSQN Fields
    issqn_tax_id = fields.Many2one(
        string="Tax ISSQN",
    )

    issqn_fg_city_id = fields.Many2one(
        string="ISSQN City",
    )

    # vDeducao
    issqn_deduction_amount = fields.Monetary(
        string='ISSQN Deduction Value',
    )

    # vOutro
    issqn_other_amount = fields.Monetary(
        string='ISSQN Other Value',
    )

    # vDescIncond
    issqn_desc_incond_amount = fields.Monetary(
        string='ISSQN Discount Incond',
    )

    # vDescCond
    issqn_desc_cond_amount = fields.Monetary(
        string='ISSQN Discount Cond',
    )

    # indISS
    issqn_eligibility = fields.Selection(
        string='ISSQN Eligibility',
    )

    # indIncentivo
    issqn_incentive = fields.Selection(
        string='ISSQN Incentive',
    )

    issqn_base = fields.Monetary(
        string="ISSQN Base",
    )

    issqn_percent = fields.Float(
        string="ISSQN %",
    )

    issqn_reduction = fields.Float(
        string="ISSQN % Reduction",
    )

    issqn_value = fields.Monetary(
        string="ISSQN Value",
    )

    issqn_wh_tax_id = fields.Many2one(
        string="Tax ISSQN RET",
    )

    issqn_wh_base = fields.Monetary(
        string="ISSQN RET Base",
    )

    issqn_wh_percent = fields.Float(
        string="ISSQN RET %",
    )

    issqn_wh_reduction = fields.Float(
        string="ISSQN RET % Reduction",
    )

    issqn_wh_value = fields.Monetary(
        string="ISSQN RET Value",
    )

    # ICMS Fields
    icms_tax_id = fields.Many2one(
        string="Tax ICMS",
    )

    icms_cst_id = fields.Many2one(
        string="CST ICMS"
    )

    icms_cst_code = fields.Char(
        string="ICMS CST Code",
    )

    icms_base_type = fields.Selection(
        string="ICMS Base Type",
    )

    icms_origin = fields.Selection(
        string="ICMS Origin",
    )

    icms_base = fields.Monetary(
        string="ICMS Base",
    )

    icms_percent = fields.Float(
        string="ICMS %",
    )

    icms_reduction = fields.Float(
        string="ICMS % Reduction",
    )

    icms_value = fields.Monetary(
        string="ICMS Value",
    )

    # motDesICMS - Motivo da desoneração do ICMS
    icms_relief_id = fields.Many2one(
        string="ICMS Relief"
    )

    # vICMSDeson - Valor do ICMS desonerado
    icms_relief_value = fields.Monetary(
        string="ICMS Relief Value",
    )

    # ICMS ST Fields
    icmsst_tax_id = fields.Many2one(
        string="Tax ICMS ST",
    )

    # modBCST - Modalidade de determinação da BC do ICMS ST
    icmsst_base_type = fields.Selection(
        string="ICMS ST Base Type",
    )

    # pMVAST - Percentual da margem de valor Adicionado do ICMS ST
    icmsst_mva_percent = fields.Float(
        string="ICMS ST MVA %",
    )

    # pRedBCST - Percentual da Redução de BC do ICMS ST
    icmsst_reduction = fields.Float(
        string="ICMS ST % Reduction",
    )

    # vBCST - Valor da BC do ICMS ST
    icmsst_base = fields.Monetary(
        string="ICMS ST Base",
    )

    # pICMSST - Alíquota do imposto do ICMS ST
    icmsst_percent = fields.Float(
        string="ICMS ST %",
    )

    # vICMSST - Valor do ICMS ST
    icmsst_value = fields.Monetary(
        string="ICMS ST Value",
    )

    icmsst_wh_base = fields.Monetary(
        string="ICMS ST WH Base",
    )

    icmsst_wh_value = fields.Monetary(
        string="ICMS ST WH Value",
    )

    # ICMS FCP Fields
    icmsfcp_tax_id = fields.Many2one(
        string="Tax ICMS FCP",
    )

    # pFCPUFDest - Percentual do ICMS relativo ao Fundo de
    # Combate à Pobreza (FCP) na UF de destino
    icmsfcp_percent = fields.Float(
        string="ICMS FCP %",
    )

    # vFCPUFDest - Valor do ICMS relativo ao Fundo
    # de Combate à Pobreza (FCP) da UF de destino
    icmsfcp_value = fields.Monetary(
        string="ICMS FCP Value",
    )

    # ICMS DIFAL Fields
    # vBCUFDest - Valor da BC do ICMS na UF de destino
    icms_destination_base = fields.Monetary(
        string="ICMS Destination Base",
    )

    # pICMSUFDest - Alíquota interna da UF de destino
    icms_origin_percent = fields.Float(
        string="ICMS Internal %",
    )

    # pICMSInter - Alíquota interestadual das UF envolvidas
    icms_destination_percent = fields.Float(
        string="ICMS External %",
    )

    # pICMSInterPart - Percentual provisório de partilha do ICMS Interestadual
    icms_sharing_percent = fields.Float(
        string="ICMS Sharing %",
    )

    # vICMSUFRemet - Valor do ICMS Interestadual para a UF do remetente
    icms_origin_value = fields.Monetary(
        string="ICMS Origin Value",
    )

    # vICMSUFDest - Valor do ICMS Interestadual para a UF de destino
    icms_destination_value = fields.Monetary(
        string="ICMS Dest. Value",
    )

    # ICMS Simples Nacional Fields
    icmssn_range_id = fields.Many2one(
        string="Simplified Range Tax",
    )

    icmssn_tax_id = fields.Many2one(
        string="Tax ICMS SN",
    )

    icmssn_base = fields.Monetary(
        string="ICMS SN Base",
    )

    icmssn_reduction = fields.Monetary(
        string="ICMS SN Reduction",
    )

    icmssn_percent = fields.Float(
        string="ICMS SN %",
    )

    icmssn_credit_value = fields.Monetary(
        string="ICMS SN Credit",
    )

    # IPI Fields
    ipi_tax_id = fields.Many2one(
        string="Tax IPI",
    )

    ipi_cst_id = fields.Many2one(
        string="CST IPI",
    )

    ipi_cst_code = fields.Char(
        string="IPI CST Code",
    )

    ipi_base_type = fields.Selection(
        string="IPI Base Type",
    )

    ipi_base = fields.Monetary(
        string="IPI Base"
    )

    ipi_percent = fields.Float(
        string="IPI %"
    )

    ipi_reduction = fields.Float(
        string="IPI % Reduction"
    )

    ipi_value = fields.Monetary(
        string="IPI Value"
    )

    ipi_guideline_id = fields.Many2one(
        string="IPI Guideline",
    )

    # II Fields
    ii_tax_id = fields.Many2one(
        string="Tax II",
    )

    ii_base = fields.Float(
        string='II Base',
    )

    ii_percent = fields.Float(
        string="II %"
    )

    ii_value = fields.Float(
        string='II Value',
    )

    ii_iof_value = fields.Float(
        string='IOF Value',
    )

    ii_customhouse_charges = fields.Float(
        string='Despesas Aduaneiras',
    )

    # PIS/COFINS Fields
    # COFINS
    cofins_tax_id = fields.Many2one(
        string="Tax COFINS",
    )

    cofins_cst_id = fields.Many2one(
        string="CST COFINS",
    )

    cofins_cst_code = fields.Char(
        string="COFINS CST Code",
    )

    cofins_base_type = fields.Selection(
        string="COFINS Base Type",
    )

    cofins_base = fields.Monetary(
        string="COFINS Base"
    )

    cofins_percent = fields.Float(
        string="COFINS %"
    )

    cofins_reduction = fields.Float(
        string="COFINS % Reduction"
    )

    cofins_value = fields.Monetary(
        string="COFINS Value"
    )

    cofins_base_id = fields.Many2one(
        string="COFINS Base Code"
    )

    cofins_credit_id = fields.Many2one(
        string="COFINS Credit Code"
    )

    # COFINS ST
    cofinsst_tax_id = fields.Many2one(
        string="Tax COFINS ST",
    )

    cofinsst_cst_id = fields.Many2one(
        string="CST COFINS ST",
    )

    cofinsst_cst_code = fields.Char(
        string="COFINS ST CST Code",
    )

    cofinsst_base_type = fields.Selection(
        string="COFINS ST Base Type",
    )

    cofinsst_base = fields.Monetary(
        string="COFINS ST Base"
    )

    cofinsst_percent = fields.Float(
        string="COFINS ST %"
    )

    cofinsst_reduction = fields.Float(
        string="COFINS ST % Reduction"
    )

    cofinsst_value = fields.Monetary(
        string="COFINS ST Value"
    )

    cofins_wh_tax_id = fields.Many2one(
        string="Tax COFINS RET",
    )

    cofins_wh_base_type = fields.Selection(
        string="COFINS WH Base Type",
    )

    cofins_wh_base = fields.Monetary(
        string="COFINS RET Base",
    )

    cofins_wh_percent = fields.Float(
        string="COFINS RET %",
    )

    cofins_wh_reduction = fields.Float(
        string="COFINS RET % Reduction",
    )

    cofins_wh_value = fields.Monetary(
        string="COFINS RET Value",
    )

    # PIS
    pis_tax_id = fields.Many2one(
        string="Tax PIS",
    )

    pis_cst_id = fields.Many2one(
        string="CST PIS",
    )

    pis_cst_code = fields.Char(
        string="PIS CST Code",
    )

    pis_base_type = fields.Selection(
        string="PIS Base Type",
    )

    pis_base = fields.Monetary(
        string="PIS Base"
    )

    pis_percent = fields.Float(
        string="PIS %"
    )

    pis_reduction = fields.Float(
        string="PIS % Reduction"
    )

    pis_value = fields.Monetary(
        string="PIS Value"
    )

    pis_base_id = fields.Many2one(
        string="PIS Base Code"
    )

    pis_credit_id = fields.Many2one(
        string="PIS Credit"
    )

    # PIS ST
    pisst_tax_id = fields.Many2one(
        string="Tax PIS ST",
    )

    pisst_cst_id = fields.Many2one(
        string="CST PIS ST",
    )

    pisst_cst_code = fields.Char(
        string="PIS ST CST Code",
    )

    pisst_base_type = fields.Selection(
        string="PIS ST Base Type",
    )

    pisst_base = fields.Monetary(
        string="PIS ST Base"
    )

    pisst_percent = fields.Float(
        string="PIS ST %"
    )

    pisst_reduction = fields.Float(
        string="PIS ST % Reduction"
    )

    pisst_value = fields.Monetary(
        string="PIS ST Value"
    )

    pis_wh_tax_id = fields.Many2one(
        string="Tax PIS RET",
    )

    pis_wh_base_type = fields.Selection(
        string="PIS WH Base Type",
    )

    pis_wh_base = fields.Monetary(
        string="PIS RET Base",
    )

    pis_wh_percent = fields.Float(
        string="PIS RET %",
    )

    pis_wh_reduction = fields.Float(
        string="PIS RET % Reduction",
    )

    pis_wh_value = fields.Monetary(
        string="PIS RET Value",
    )

    # CSLL Fields
    csll_tax_id = fields.Many2one(
        string="Tax CSLL",
    )

    csll_base = fields.Monetary(
        string="CSLL Base",
    )

    csll_percent = fields.Float(
        string="CSLL %",
    )

    csll_reduction = fields.Float(
        string="CSLL % Reduction",
    )

    csll_value = fields.Monetary(
        string="CSLL Value",
    )

    csll_wh_tax_id = fields.Many2one(
        string="Tax CSLL RET",
    )

    csll_wh_base = fields.Monetary(
        string="CSLL RET Base",
    )

    csll_wh_percent = fields.Float(
        string="CSLL RET %",
    )

    csll_wh_reduction = fields.Float(
        string="CSLL RET % Reduction",
    )

    csll_wh_value = fields.Monetary(
        string="CSLL RET Value",
    )

    irpj_tax_id = fields.Many2one(
        string="Tax IRPJ",
    )

    irpj_base = fields.Monetary(
        string="IRPJ Base",
    )

    irpj_percent = fields.Float(
        string="IRPJ %",
    )

    irpj_reduction = fields.Float(
        string="IRPJ % Reduction",
    )

    irpj_value = fields.Monetary(
        string="IRPJ Value",
    )

    irpj_wh_tax_id = fields.Many2one(
        string="Tax IRPJ RET",
    )

    irpj_wh_base = fields.Monetary(
        string="IRPJ RET Base",
    )

    irpj_wh_percent = fields.Float(
        string="IRPJ RET %",
    )

    irpj_wh_reduction = fields.Float(
        string="IRPJ RET % Reduction",
    )

    irpj_wh_value = fields.Monetary(
        string="IRPJ RET Value",
    )

    inss_tax_id = fields.Many2one(
        string="Tax INSS",
    )

    inss_base = fields.Monetary(
        string="INSS Base",
    )

    inss_percent = fields.Float(
        string="INSS %",
    )

    inss_reduction = fields.Float(
        string="INSS % Reduction",
    )

    inss_value = fields.Monetary(
        string="INSS Value",
    )

    inss_wh_tax_id = fields.Many2one(
        string="Tax INSS RET",
    )

    inss_wh_base = fields.Monetary(
        string="INSS RET Base",
    )

    inss_wh_percent = fields.Float(
        string="INSS RET %",
    )

    inss_wh_reduction = fields.Float(
        string="INSS RET % Reduction",
    )

    inss_wh_value = fields.Monetary(
        string="INSS RET Value",
    )

    simple_value = fields.Monetary(
        string="National Simple Taxes",
    )

    simple_without_icms_value = fields.Monetary(
        string="National Simple Taxes without ICMS",
    )

    comment_ids = fields.Many2many(
        string='Comments',
    )
