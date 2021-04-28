# Copyright 2020 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _


class L10n_br_fiscalDocumentLineMixin(models.AbstractModel):

    _inherit = 'l10n_br_fiscal.document.line.mixin'

    currency_id = fields.Many2one(
        string="Moeda",
    )

    product_id = fields.Many2one(
        string="Produto"
    )

    tax_icms_or_issqn = fields.Selection(
        string='Imposto ICMS ou ISSQN',
    )

    price_unit = fields.Float(
        string="Preço unitário",
    )

    partner_id = fields.Many2one(
        string="Parceiro")

    partner_company_type = fields.Selection(
        string='Tipo da Empresa',
    )

    uom_id = fields.Many2one(
        string="UOM"
    )

    quantity = fields.Float(
        string="Quantidade",
    )

    fiscal_type = fields.Selection(
        string="Tipo Fiscal")

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
        string="Operação",
    )

    fiscal_operation_type = fields.Selection(
        string="Tipo da Operação Fiscal"
    )

    fiscal_operation_line_id = fields.Many2one(
        string="Linha da Operação",
    )

    cfop_id = fields.Many2one(
        string="CFOP",
    )

    cfop_destination = fields.Selection(
        string="Destino da CFOP"
    )

    fiscal_price = fields.Float(
        string="Preço Fiscal",
    )

    uot_id = fields.Many2one(
        string="Unidade de medida do imposto")

    fiscal_quantity = fields.Float(
        string="Quantidade Fiscal",
    )

    discount_value = fields.Monetary(
        string="Valor do Desconto",
    )

    insurance_value = fields.Monetary(
        string='Valor do Seguro',
    )

    other_costs_value = fields.Monetary(
        string='Outros Custos',
    )

    freight_value = fields.Monetary(
        string='Valor do Frete',
    )

    fiscal_tax_ids = fields.Many2many(
        string="Impostos Fiscais"
    )

    amount_tax_not_included = fields.Monetary(
        string="Total sem impostos",
    )

    amount_tax_withholding = fields.Monetary(
        string="Total do imposto retido",
    )

    fiscal_genre_id = fields.Many2one(
        string="Gênero do produto")

    fiscal_genre_code = fields.Char(
        string="Código do Gênero Fiscal"
    )

    service_type_id = fields.Many2one(
        string="Tipo do Serviço",
    )

    partner_order = fields.Char(
        string='Partner Order (xPed)',
    )

    partner_order_line = fields.Char(
        string='Partner Order Line (nItemPed)',
    )

    # ISSQN Fields
    issqn_tax_id = fields.Many2one(
        string="Imposto ISSQN",
    )

    issqn_fg_city_id = fields.Many2one(
        string="Cidade do ISSQN",
    )

    # vDeducao
    issqn_deduction_amount = fields.Monetary(
        string='Valor da dedução do ISSQN',
    )

    # vOutro
    issqn_other_amount = fields.Monetary(
        string='Outros valores do ISSQN',
    )

    # vDescIncond
    issqn_desc_incond_amount = fields.Monetary(
        string='Disconto incondicional do ISSQN',
    )

    # vDescCond
    issqn_desc_cond_amount = fields.Monetary(
        string='Desconto incondicional do ISSQN',
    )

    # indISS
    issqn_eligibility = fields.Selection(
        string='Eligibilidade do ISSQN',
    )

    # indIncentivo
    issqn_incentive = fields.Selection(
        string='Incentivo de ISSQN',
    )

    issqn_base = fields.Monetary(
        string="Base do ISSQN",
    )

    issqn_percent = fields.Float(
        string="ISSQN %",
    )

    issqn_reduction = fields.Float(
        string="ISSQN % Redução",
    )

    issqn_value = fields.Monetary(
        string="Valor ISSQN",
    )

    issqn_wh_tax_id = fields.Many2one(
        string="Retenção do Imposto ISSQN",
    )

    issqn_wh_base = fields.Monetary(
        string="Base da retenção do ISSQN",
    )

    issqn_wh_percent = fields.Float(
        string="Retenção do ISSQN %",
    )

    issqn_wh_reduction = fields.Float(
        string="Redução % da retenção do ISSQN",
    )

    issqn_wh_value = fields.Monetary(
        string="Valor da retenção do ISSQN",
    )

    # ICMS Fields
    icms_tax_id = fields.Many2one(
        string="Imposto ICMS",
    )

    icms_cst_id = fields.Many2one(
        string="CST ICMS"
    )

    icms_cst_code = fields.Char(
        string="Código CST ICMS",
    )

    icms_base_type = fields.Selection(
        string="Tipo da base do ICMS",
    )

    icms_origin = fields.Selection(
        string="Origem do ICMS",
    )

    icms_base = fields.Monetary(
        string="Base do ICMS",
    )

    icms_percent = fields.Float(
        string="ICMS %",
    )

    icms_reduction = fields.Float(
        string="Redução % do ICMS",
    )

    icms_value = fields.Monetary(
        string="Valor do ICMS",
    )

    # motDesICMS - Motivo da desoneração do ICMS
    icms_relief_id = fields.Many2one(
        string="Motivo da desoneração do ICMS"
    )

    # vICMSDeson - Valor do ICMS desonerado
    icms_relief_value = fields.Monetary(
        string="Valor do ICMS desonerado",
    )

    # ICMS ST Fields
    icmsst_tax_id = fields.Many2one(
        string="Imposto ICMS ST",
    )

    # modBCST - Modalidade de determinação da BC do ICMS ST
    icmsst_base_type = fields.Selection(
        string="Tipo da base do ICMS ST",
    )

    # pMVAST - Percentual da margem de valor Adicionado do ICMS ST
    icmsst_mva_percent = fields.Float(
        string="ICMS ST MVA %",
    )

    # pRedBCST - Percentual da Redução de BC do ICMS ST
    icmsst_reduction = fields.Float(
        string="Redução % do ICMS ST",
    )

    # vBCST - Valor da BC do ICMS ST
    icmsst_base = fields.Monetary(
        string="Base do ICMS ST",
    )

    # pICMSST - Alíquota do imposto do ICMS ST
    icmsst_percent = fields.Float(
        string="ICMS ST %",
    )

    # vICMSST - Valor do ICMS ST
    icmsst_value = fields.Monetary(
        string="Valor do ICMS ST",
    )

    icmsst_wh_base = fields.Monetary(
        string="Base da retenção do ICMS ST",
    )

    icmsst_wh_value = fields.Monetary(
        string="Valor da retenção do ICMS ST",
    )

    # ICMS FCP Fields
    icmsfcp_tax_id = fields.Many2one(
        string="ICMS FCP",
    )

    # pFCPUFDest - Percentual do ICMS relativo ao Fundo de
    # Combate à Pobreza (FCP) na UF de destino
    icmsfcp_percent = fields.Float(
        string="ICMS FCP %",
    )

    # vFCPUFDest - Valor do ICMS relativo ao Fundo
    # de Combate à Pobreza (FCP) da UF de destino
    icmsfcp_value = fields.Monetary(
        string="Valor do ICMS FCP",
    )

    # ICMS DIFAL Fields
    # vBCUFDest - Valor da BC do ICMS na UF de destino
    icms_destination_base = fields.Monetary(
        string="ICMS Base de Destino",
    )

    # pICMSUFDest - Alíquota interna da UF de destino
    icms_origin_percent = fields.Float(
        string="% ICMS Interno",
    )

    # pICMSInter - Alíquota interestadual das UF envolvidas
    icms_destination_percent = fields.Float(
        string="% ICSM Externo",
    )

    # pICMSInterPart - Percentual provisório de partilha do ICMS Interestadual
    icms_sharing_percent = fields.Float(
        string="% Partilha interestadual do ICMS",
    )

    # vICMSUFRemet - Valor do ICMS Interestadual para a UF do remetente
    icms_origin_value = fields.Monetary(
        string="Valor do ICMS na UF de origem",
    )

    # vICMSUFDest - Valor do ICMS Interestadual para a UF de destino
    icms_destination_value = fields.Monetary(
        string="Valor do ICMS na UF de destino",
    )

    # ICMS Simples Nacional Fields
    icmssn_range_id = fields.Many2one(
        string="Faixa do Simples Nacional",
    )

    icmssn_tax_id = fields.Many2one(
        string="Imposto ICMS SN",
    )

    icmssn_base = fields.Monetary(
        string="Base do ICMS SN",
    )

    icmssn_reduction = fields.Monetary(
        string="Redução do ICMS SN",
    )

    icmssn_percent = fields.Float(
        string="ICMS SN %",
    )

    icmssn_credit_value = fields.Monetary(
        string="Crédito de ICMS SN",
    )

    # IPI Fields
    ipi_tax_id = fields.Many2one(
        string="Imposto IPI",
    )

    ipi_cst_id = fields.Many2one(
        string="CST IPI",
    )

    ipi_cst_code = fields.Char(
        string="Código CST IPI",
    )

    ipi_base_type = fields.Selection(
        string="Tipo da base do IPI",
    )

    ipi_base = fields.Monetary(
        string="Base do IPI"
    )

    ipi_percent = fields.Float(
        string="IPI %"
    )

    ipi_reduction = fields.Float(
        string="Redução % do IPI "
    )

    ipi_value = fields.Monetary(
        string="Valor do IPI"
    )

    ipi_guideline_id = fields.Many2one(
        string="Enquadramento Legal do IPI",
    )

    # II Fields
    ii_tax_id = fields.Many2one(
        string="Imposto II",
    )

    ii_base = fields.Float(
        string='Base do II',
    )

    ii_percent = fields.Float(
        string="II %"
    )

    ii_value = fields.Float(
        string='Valor do II',
    )

    ii_iof_value = fields.Float(
        string='Valor do IOF',
    )

    ii_customhouse_charges = fields.Float(
        string='Despesas Aduaneiras',
    )

    # PIS/COFINS Fields
    # COFINS
    cofins_tax_id = fields.Many2one(
        string="Imposto COFINS",
    )

    cofins_cst_id = fields.Many2one(
        string="CST COFINS",
    )

    cofins_cst_code = fields.Char(
        string="Código CST COFINS",
    )

    cofins_base_type = fields.Selection(
        string="Tipo da base do COFINS",
    )

    cofins_base = fields.Monetary(
        string="Base do COFINS"
    )

    cofins_percent = fields.Float(
        string="COFINS %"
    )

    cofins_reduction = fields.Float(
        string="Redução % do COFINS"
    )

    cofins_value = fields.Monetary(
        string="Valor do COFINS"
    )

    cofins_base_id = fields.Many2one(
        string="COFINS Cód. da Base"
    )

    cofins_credit_id = fields.Many2one(
        string="COFINS Cód. Crédito"
    )

    # COFINS ST
    cofinsst_tax_id = fields.Many2one(
        string="Imposto COFINS ST",
    )

    cofinsst_cst_id = fields.Many2one(
        string="CST COFINS ST",
    )

    cofinsst_cst_code = fields.Char(
        string="Código CST COFINS ST",
    )

    cofinsst_base_type = fields.Selection(
        string="Tipo da base do COFINS ST",
    )

    cofinsst_base = fields.Monetary(
        string="Base do COFINS ST"
    )

    cofinsst_percent = fields.Float(
        string="COFINS ST %"
    )

    cofinsst_reduction = fields.Float(
        string="Redução % do COFINS ST"
    )

    cofinsst_value = fields.Monetary(
        string="Valor do COFINS ST"
    )

    cofins_wh_tax_id = fields.Many2one(
        string="COFINS RET",
    )

    cofins_wh_base_type = fields.Selection(
        string="Tipo da base do COFINS RET",
    )

    cofins_wh_base = fields.Monetary(
        string="Base do COFINS RET",
    )

    cofins_wh_percent = fields.Float(
        string="COFINS RET %",
    )

    cofins_wh_reduction = fields.Float(
        string="Redução % do COFINS RET",
    )

    cofins_wh_value = fields.Monetary(
        string="Valor do COFINS RET",
    )

    # PIS
    pis_tax_id = fields.Many2one(
        string="Imposto PIS",
    )

    pis_cst_id = fields.Many2one(
        string="CST PIS",
    )

    pis_cst_code = fields.Char(
        string="Código CST PIS",
    )

    pis_base_type = fields.Selection(
        string="Tipo da base do PIS",
    )

    pis_base = fields.Monetary(
        string="Base do PIS"
    )

    pis_percent = fields.Float(
        string="PIS %"
    )

    pis_reduction = fields.Float(
        string="Redução % do PIS"
    )

    pis_value = fields.Monetary(
        string="Valor do PIS"
    )

    pis_base_id = fields.Many2one(
        string="PIS Código da base"
    )

    pis_credit_id = fields.Many2one(
        string="Crédito PIS"
    )

    # PIS ST
    pisst_tax_id = fields.Many2one(
        string="Imposto PIS ST",
    )

    pisst_cst_id = fields.Many2one(
        string="CST PIS ST",
    )

    pisst_cst_code = fields.Char(
        string="Código CST PIS ST",
    )

    pisst_base_type = fields.Selection(
        string="Tipo da base do PIS ST",
    )

    pisst_base = fields.Monetary(
        string="Base do PIS ST"
    )

    pisst_percent = fields.Float(
        string="PIS ST %"
    )

    pisst_reduction = fields.Float(
        string="Redução % do PIS ST"
    )

    pisst_value = fields.Monetary(
        string="Valor do PIS ST"
    )

    pis_wh_tax_id = fields.Many2one(
        string="Imposto PIS RET",
    )

    pis_wh_base_type = fields.Selection(
        string="Tipo da base do PIS RET",
    )

    pis_wh_base = fields.Monetary(
        string="Base do PIS RET",
    )

    pis_wh_percent = fields.Float(
        string="PIS RET %",
    )

    pis_wh_reduction = fields.Float(
        string="Redução % do PIS RET",
    )

    pis_wh_value = fields.Monetary(
        string="Valor do PIS RET",
    )

    # CSLL Fields
    csll_tax_id = fields.Many2one(
        string="Imposto CSLL",
    )

    csll_base = fields.Monetary(
        string="Base do CSLL",
    )

    csll_percent = fields.Float(
        string="CSLL %",
    )

    csll_reduction = fields.Float(
        string="Redução % do CSLL",
    )

    csll_value = fields.Monetary(
        string="Valor do CSLL",
    )

    csll_wh_tax_id = fields.Many2one(
        string="Imposto CSLL RET",
    )

    csll_wh_base = fields.Monetary(
        string="Base do CSLL RET",
    )

    csll_wh_percent = fields.Float(
        string="CSLL RET %",
    )

    csll_wh_reduction = fields.Float(
        string="Redução % do CSLL RET",
    )

    csll_wh_value = fields.Monetary(
        string="Valor do CSLL RET",
    )

    irpj_tax_id = fields.Many2one(
        string="Imposto IRPJ",
    )

    irpj_base = fields.Monetary(
        string="Base do IRPJ",
    )

    irpj_percent = fields.Float(
        string="IRPJ %",
    )

    irpj_reduction = fields.Float(
        string="Redução % do IRPJ",
    )

    irpj_value = fields.Monetary(
        string="Valor do IRPJ",
    )

    irpj_wh_tax_id = fields.Many2one(
        string="Imposto IRPJ RET",
    )

    irpj_wh_base = fields.Monetary(
        string="Base do IRPJ RET",
    )

    irpj_wh_percent = fields.Float(
        string="IRPJ RET %",
    )

    irpj_wh_reduction = fields.Float(
        string="Redução % do IRPJ RET",
    )

    irpj_wh_value = fields.Monetary(
        string="Valor do IRPJ RET",
    )

    inss_tax_id = fields.Many2one(
        string="Imposto INSS",
    )

    inss_base = fields.Monetary(
        string="Base do INSS",
    )

    inss_percent = fields.Float(
        string="INSS %",
    )

    inss_reduction = fields.Float(
        string="Redução % do INSS",
    )

    inss_value = fields.Monetary(
        string="Valor do INSS",
    )

    inss_wh_tax_id = fields.Many2one(
        string="Imposto INSS RET",
    )

    inss_wh_base = fields.Monetary(
        string="Base do INSS RET",
    )

    inss_wh_percent = fields.Float(
        string="INSS RET %",
    )

    inss_wh_reduction = fields.Float(
        string="Redução % do INSS RET",
    )

    inss_wh_value = fields.Monetary(
        string="Valor do INSS RET",
    )

    simple_value = fields.Monetary(
        string="Impostos do Simples Nacional",
    )

    simple_without_icms_value = fields.Monetary(
        string="Impostos do Simples Nacional sem o ICMS",
    )

    comment_ids = fields.Many2many(
        string='Comentários',
    )
