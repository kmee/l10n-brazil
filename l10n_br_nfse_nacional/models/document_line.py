# Copyright 2026 Akretion - Raphaël Valyi <raphael.valyi@akretion.com>
# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re

from odoo import _, api, fields

from odoo.addons.l10n_br_fiscal.constants.fiscal import TAX_FRAMEWORK_SIMPLES_ALL
from odoo.addons.spec_driven_model.models import spec_models

from ..constants.nfse_nacional import (
    IBSCBS_CLASS_TRIB_DEFAULT,
    IBSCBS_CST_DEFAULT,
    ISSQN_ELIGIBILITY_TO_TP_SUSP,
    ISSQN_ELIGIBILITY_TO_TRIB_ISSQN,
    TP_RET_PIS_COFINS,
)

# xDescServ is a TSDesc2000 in the schema: 2000 characters. The composed
# description of the real note runs about 330, so the cut is a safety net
# rather than a business rule.
XDESCSERV_MAX_LENGTH = 2000


class L10nBrFiscalDocumentLine(spec_models.SpecModel):
    _name = "l10n_br_fiscal.document.line"
    _inherit = [
        "l10n_br_fiscal.document.line",
        # serv
        "nfse.10.tcserv",
        "nfse.10.tclocprest",
        "nfse.10.tccserv",
        # valores
        "nfse.10.tcinfovalores",
        "nfse.10.tcvservprest",
        "nfse.10.tcvdesccondincond",
        "nfse.10.tcinfotributacao",
        "nfse.10.tctribmunicipal",
        "nfse.10.tcexigsuspensa",
        "nfse.10.tcbeneficiomunicipal",
        "nfse.10.tccomexterior",
        "nfse.10.tctribfederal",
        "nfse.10.tctriboutrospiscofins",
        "nfse.10.tctribtotal",
        "nfse.10.tctribtotalmonet",
        "nfse.10.tctribtotalpercent",
    ]

    _nfse10_odoo_module = (
        "odoo.addons.l10n_br_nfse_spec.models.v1_0.tipos_complexos_v1_01"
    )
    _nfse10_binding_module = "nfelib.nfse.bindings.v1_0.tipos_complexos_v1_01"
    _nfse10_binding_type_serv = "Tcserv"
    _nfse10_binding_type_valores = "TcinfoValores"
    _nfse10_binding_type_vServPrest = "TcvservPrest"
    _nfse10_binding_type_vDescCondIncond = "TcvdescCondIncond"
    _nfse10_binding_type_trib = "TcinfoTributacao"  # TODO sure?
    _nfse10_binding_type_piscofins = "TctribOutrosPisCofins"
    _nfse10_binding_type_locPrest = "TclocPrest"
    _nfse10_binding_type_cServ = "Tccserv"
    _nfse10_binding_type_tribMun = "TctribMunicipal"
    _nfse10_binding_type_exigSusp = "TcexigSuspensa"
    _nfse10_binding_type_BM = "TcbeneficioMunicipal"
    _nfse10_binding_type_comExt = "TccomExterior"
    # In 1.01 TCTribNacional became TCTribFederal (nfelib PR #105, "TribNac
    # renamed to tribFed"). The tag name stays tribFed in both versions.
    _nfse10_binding_type_tribFed = "TctribFederal"
    _nfse10_binding_type_totTrib = "TctribTotal"
    _nfse10_binding_type_vTotTrib = "TctribTotalMonet"
    _nfse10_binding_type_pTotTrib = "TctribTotalPercent"

    nfse10_locPrest = fields.Many2one(
        "l10n_br_fiscal.document.line",
        compute="_compute_nfse10_self",
        string="Local Prestação",
    )
    nfse10_cServ = fields.Many2one(
        "l10n_br_fiscal.document.line",
        compute="_compute_nfse10_self",
        string="Código Serviço",
    )
    nfse10_vServPrest = fields.Many2one(
        "l10n_br_fiscal.document.line",
        compute="_compute_nfse10_self",
        string="Valores Serviço",
    )
    nfse10_vDescCondIncond = fields.Many2one(
        "l10n_br_fiscal.document.line",
        compute="_compute_nfse10_self",
        string="Descontos",
    )
    nfse10_trib = fields.Many2one(
        "l10n_br_fiscal.document.line",
        compute="_compute_nfse10_self",
        string="Tributação",
    )
    nfse10_tribMun = fields.Many2one(
        "l10n_br_fiscal.document.line",
        compute="_compute_nfse10_self",
        string="Tributos Municipais",
    )
    nfse10_exigSusp = fields.Many2one(
        "l10n_br_fiscal.document.line",
        compute="_compute_nfse10_self",
        string="Exigibilidade Suspensa",
    )
    nfse10_BM = fields.Many2one(
        "l10n_br_fiscal.document.line",
        compute="_compute_nfse10_self",
        string="Benefício Municipal",
    )
    nfse10_comExt = fields.Many2one(
        "l10n_br_fiscal.document.line",
        compute="_compute_nfse10_self",
        string="Comércio Exterior",
    )
    nfse10_tribFed = fields.Many2one(
        "l10n_br_fiscal.document.line",
        compute="_compute_nfse10_self",
        string="Tributos Federais",
    )
    nfse10_piscofins = fields.Many2one(
        "l10n_br_fiscal.document.line",
        compute="_compute_nfse10_self",
        string="PIS/COFINS",
    )
    nfse10_totTrib = fields.Many2one(
        "l10n_br_fiscal.document.line",
        compute="_compute_nfse10_self",
        string="Total Tributos",
    )

    # Fields mapped to tags
    # Local da PRESTACAO, nao do fato gerador do ISSQN: ver issqn_service_city_id
    # em l10n_br_fiscal. Era related do fato gerador, que cai na cidade da empresa
    # quando nao ha codigo municipal, e por isso a nota saia sempre com o municipio
    # do emitente.
    nfse10_cLocPrestacao = fields.Char(related="issqn_service_city_id.ibge_code")
    nfse10_cTribNac = fields.Char(related="national_taxation_code_id.code")
    nfse10_cTribMun = fields.Char(related="city_taxation_code_id.code")
    # O cadastro de NBS guarda o codigo com mascara ("1.2001.50.00") porque e
    # assim que ele e exibido, e o layout quer os 9 digitos crus ("120015000").
    # Conferido na nota real 28 da Zitron, cuja tag traz sem separador e cujo
    # DANFSE imprime com.
    nfse10_cNBS = fields.Char(compute="_compute_nfse10_cnbs")

    @api.depends("nbs_id.code")
    def _compute_nfse10_cnbs(self):
        for rec in self:
            rec.nfse10_cNBS = re.sub(r"\D", "", rec.nbs_id.code or "") or False

    # A NFS-e nao tem tag de informacao adicional por item: o que a nota carrega do
    # servico e o xDescServ, e nada mais. E ha cliente que exige ali o boletim de
    # medicao, o contrato, o pedido, a competencia, o centro de custo, o vencimento e
    # os dados bancarios — foi assim na nota real 28 da Zitron, emitida por fora.
    #
    # `additional_data` da linha ja e o texto renderizado dos comentarios fiscais de
    # linha (l10n_br_fiscal.comment com object de linha), que sao TEMPLATE Jinja com
    # `doc` e `item` no contexto e vem configurados na propria linha de operacao. O
    # `manual_additional_data` entra na mesma renderizacao, para a parte que muda por
    # nota. Faltava so levar isso ao xDescServ.
    #
    # Quando ha texto composto ele SUBSTITUI o nome, em vez de se somar: a nota real
    # nao prefixa nome de produto, e um template que queira o nome escreve
    # ${item.name}. Sem comentario nenhum, cai no nome da linha, que e o de hoje.
    nfse10_xDescServ = fields.Char(compute="_compute_nfse10_xdescserv")

    @api.depends("name", "additional_data")
    def _compute_nfse10_xdescserv(self):
        for rec in self:
            texto = (rec.additional_data or "").strip() or (rec.name or "").strip()
            rec.nfse10_xDescServ = texto[:XDESCSERV_MAX_LENGTH] or False

    nfse10_vServ = fields.Char(compute="_compute_nfse10_valores")
    nfse10_vDescIncond = fields.Char(compute="_compute_nfse10_valores")
    nfse10_vDescCond = fields.Char(compute="_compute_nfse10_valores")

    nfse10_tribISSQN = fields.Selection(
        compute="_compute_nfse10_tribISSQN",
        store=True,
        readonly=False,
    )

    @api.depends("issqn_eligibility")
    def _compute_nfse10_tribISSQN(self):
        for record in self:
            record.nfse10_tribISSQN = ISSQN_ELIGIBILITY_TO_TRIB_ISSQN.get(
                record.issqn_eligibility, "1"
            )

    nfse10_tpImunidade = fields.Selection(
        compute="_compute_nfse10_trib_mun",
        store=True,
        readonly=False,
    )
    nfse10_cPaisResult = fields.Char(
        compute="_compute_nfse10_trib_mun",
        store=True,
        readonly=False,
    )
    nfse10_tpSusp = fields.Selection(
        compute="_compute_nfse10_trib_mun",
        store=True,
        readonly=False,
    )

    nfse10_tpRetISSQN = fields.Selection(compute="_compute_nfse10_trib_mun")
    nfse10_pAliq = fields.Char(compute="_compute_nfse10_trib_mun")

    nfse10_vRetCP = fields.Char(compute="_compute_nfse10_trib_fed")
    nfse10_vRetIRRF = fields.Char(compute="_compute_nfse10_trib_fed")
    nfse10_vRetCSLL = fields.Char(compute="_compute_nfse10_trib_fed")

    nfse10_CST = fields.Selection(compute="_compute_nfse10_pis_cofins")
    nfse10_vBCPisCofins = fields.Char(compute="_compute_nfse10_pis_cofins")
    nfse10_pAliqPis = fields.Char(compute="_compute_nfse10_pis_cofins")
    nfse10_pAliqCofins = fields.Char(compute="_compute_nfse10_pis_cofins")
    nfse10_vPis = fields.Char(compute="_compute_nfse10_pis_cofins")
    nfse10_vCofins = fields.Char(compute="_compute_nfse10_pis_cofins")
    nfse10_tpRetPisCofins = fields.Selection(compute="_compute_nfse10_pis_cofins")

    nfse10_indTotTrib = fields.Selection(compute="_compute_nfse10_tot_trib")
    nfse10_pTotTribSN = fields.Char(compute="_compute_nfse10_tot_trib")
    nfse10_pTotTrib = fields.Many2one(
        "l10n_br_fiscal.document.line",
        compute="_compute_nfse10_tot_trib",
        string="Percentual Total de Tributos",
    )
    nfse10_pTotTribFed = fields.Char(compute="_compute_nfse10_tot_trib")
    nfse10_pTotTribEst = fields.Char(compute="_compute_nfse10_tot_trib")
    nfse10_pTotTribMun = fields.Char(compute="_compute_nfse10_tot_trib")
    nfse10_vTotTrib = fields.Many2one(
        "l10n_br_fiscal.document.line",
        compute="_compute_nfse10_tot_trib",
        string="Valor Total de Tributos",
    )
    nfse10_vTotTribFed = fields.Char(compute="_compute_nfse10_tot_trib")
    nfse10_vTotTribEst = fields.Char(compute="_compute_nfse10_tot_trib")
    nfse10_vTotTribMun = fields.Char(compute="_compute_nfse10_tot_trib")

    @api.depends("discount_value", "issqn_desc_cond_amount", "issqn_eligibility")
    def _compute_nfse10_self(self):
        for rec in self:
            rec.nfse10_locPrest = rec.id
            rec.nfse10_cServ = rec.id
            rec.nfse10_vServPrest = rec.id
            # Grupo opcional: apontar sempre para o registro serializa
            # <vDescCondIncond/> vazio, porque os dois filhos ficam False quando nao ha
            # desconto. Tag vazia e recusa no XSD.
            rec.nfse10_vDescCondIncond = (
                rec.id if (rec.discount_value or rec.issqn_desc_cond_amount) else False
            )
            rec.nfse10_trib = rec.id
            rec.nfse10_tribMun = rec.id
            rec.nfse10_exigSusp = (
                rec.id if rec.issqn_eligibility in ("6", "7") else False
            )
            rec.nfse10_BM = rec.id if rec.issqn_eligibility == "3" else False
            rec.nfse10_comExt = rec.id if rec.issqn_eligibility == "4" else False
            rec.nfse10_tribFed = rec.id
            rec.nfse10_piscofins = rec.id
            rec.nfse10_totTrib = rec.id

    @api.depends("price_gross", "discount_value", "issqn_desc_cond_amount")
    def _compute_nfse10_valores(self):
        for rec in self:
            rec.nfse10_vServ = f"{rec.price_gross:.2f}" if rec.price_gross else False
            rec.nfse10_vDescIncond = (
                f"{rec.discount_value:.2f}" if rec.discount_value else False
            )
            rec.nfse10_vDescCond = (
                f"{rec.issqn_desc_cond_amount:.2f}"
                if rec.issqn_desc_cond_amount
                else False
            )

    @api.depends("issqn_wh_value", "issqn_eligibility", "partner_id.country_id")
    def _compute_nfse10_trib_mun(self):
        # pAliq is optional and the ISSQN rate comes from the municipality
        # register inside the ADN, which applies it to the declared base.
        # Sending it again only diverges the day the municipality changes it.
        for rec in self:
            rec.nfse10_pAliq = False
            rec.nfse10_tpRetISSQN = "2" if rec.issqn_wh_value > 0 else "1"
            rec.nfse10_tpImunidade = "0" if rec.issqn_eligibility == "5" else False
            rec.nfse10_cPaisResult = (
                rec.partner_id.country_id.code
                if rec.issqn_eligibility == "4"
                else False
            )
            rec.nfse10_tpSusp = ISSQN_ELIGIBILITY_TO_TP_SUSP.get(
                rec.issqn_eligibility, False
            )

    def _nfse10_csrf_withholding(self):
        self.ensure_one()
        return self.csll_wh_value + self.pis_wh_value + self.cofins_wh_value

    def _nfse10_federal_withholding(self):
        self.ensure_one()
        return self.irpj_wh_value + self._nfse10_csrf_withholding()

    @api.depends(
        "inss_wh_value",
        "irpj_wh_value",
        "csll_wh_value",
        "pis_wh_value",
        "cofins_wh_value",
    )
    def _compute_nfse10_trib_fed(self):
        # tribFed holds no monetary field for the PIS/COFINS withheld: the
        # layout only flags them in tpRetPisCofins. The CSRF of Lei 10.833
        # art. 30 is therefore declared as a single amount in vRetCSLL, which
        # is what makes vTotalRet on the DANFSE close.
        for rec in self:
            csrf = rec._nfse10_csrf_withholding()
            rec.nfse10_vRetCP = (
                f"{rec.inss_wh_value:.2f}" if rec.inss_wh_value else False
            )
            rec.nfse10_vRetIRRF = (
                f"{rec.irpj_wh_value:.2f}" if rec.irpj_wh_value else False
            )
            rec.nfse10_vRetCSLL = f"{csrf:.2f}" if csrf else False

    @api.depends(
        "pis_cst_code",
        "pis_base",
        "cofins_base",
        "pis_percent",
        "cofins_percent",
        "pis_value",
        "cofins_value",
        "pis_wh_value",
        "cofins_wh_value",
        "csll_wh_value",
    )
    def _compute_nfse10_pis_cofins(self):
        valid_cst = dict(self._fields["nfse10_CST"].selection)
        for rec in self:
            cst = rec.pis_cst_code
            rec.nfse10_CST = cst if cst in valid_cst else "00"
            base = rec.pis_base or rec.cofins_base or 0.0
            rec.nfse10_vBCPisCofins = f"{base:.2f}" if base else False
            rec.nfse10_pAliqPis = f"{rec.pis_percent:.2f}" if rec.pis_percent else False
            rec.nfse10_pAliqCofins = (
                f"{rec.cofins_percent:.2f}" if rec.cofins_percent else False
            )
            rec.nfse10_vPis = f"{rec.pis_value:.2f}" if rec.pis_value else False
            rec.nfse10_vCofins = (
                f"{rec.cofins_value:.2f}" if rec.cofins_value else False
            )
            rec.nfse10_tpRetPisCofins = TP_RET_PIS_COFINS[
                (
                    bool(rec.pis_wh_value),
                    bool(rec.cofins_wh_value),
                    bool(rec.csll_wh_value),
                )
            ]

    @api.depends(
        "company_id.tax_framework",
        "company_id.simplified_tax_range_id.total_tax_percent",
        "irpj_wh_value",
        "csll_wh_value",
        "pis_wh_value",
        "cofins_wh_value",
        "issqn_value",
    )
    def _compute_nfse10_tot_trib(self):
        # totTrib is a required xs:choice between vTotTrib, pTotTrib,
        # indTotTrib and pTotTribSN. Rejection E0713 of the national
        # environment bars indTotTrib and pTotTribSN outside Simples Nacional,
        # which therefore declares the burden as an amount in vTotTrib.
        for rec in self:
            simples = rec.company_id.tax_framework in TAX_FRAMEWORK_SIMPLES_ALL
            percent = (
                rec.company_id.simplified_tax_range_id.total_tax_percent
                if simples
                else 0.0
            )
            rec.nfse10_pTotTrib = False
            rec.nfse10_pTotTribFed = False
            rec.nfse10_pTotTribEst = False
            rec.nfse10_pTotTribMun = False
            if simples:
                rec.nfse10_indTotTrib = False if percent else "0"
                rec.nfse10_pTotTribSN = f"{percent:.2f}" if percent else False
                rec.nfse10_vTotTrib = False
                rec.nfse10_vTotTribFed = False
                rec.nfse10_vTotTribEst = False
                rec.nfse10_vTotTribMun = False
            else:
                rec.nfse10_indTotTrib = False
                rec.nfse10_pTotTribSN = False
                rec.nfse10_vTotTrib = rec.id
                rec.nfse10_vTotTribFed = f"{rec._nfse10_federal_withholding():.2f}"
                rec.nfse10_vTotTribEst = "0.00"
                rec.nfse10_vTotTribMun = f"{rec.issqn_value or 0.0:.2f}"

    def _nfse10_ibscbs_cst(self):
        self.ensure_one()
        if self.ibs_cst_id.code:
            return self.ibs_cst_id.code
        if self.cbs_cst_id.code:
            return self.cbs_cst_id.code
        if self.tax_classification_id.code:
            return self.tax_classification_id.code.zfill(6)[:3]
        return IBSCBS_CST_DEFAULT

    def _nfse10_ibscbs_class_trib(self):
        self.ensure_one()
        if self.tax_classification_id.code:
            return self.tax_classification_id.code.zfill(6)
        return IBSCBS_CLASS_TRIB_DEFAULT

    def _nfse10_com_ext_missing_fields(self):
        self.ensure_one()
        required = (
            "nfse10_mdPrestacao",
            "nfse10_vincPrest",
            "nfse10_tpMoeda",
            "nfse10_vServMoeda",
            "nfse10_mecAFComexP",
            "nfse10_mecAFComexT",
            "nfse10_movTempBens",
            "nfse10_mdic",
        )
        return [field_name for field_name in required if not self[field_name]]

    def _nfse10_issqn_situation_errors(self):
        self.ensure_one()
        errors = []
        if self.nfse10_tribISSQN == "3":
            missing = self._nfse10_com_ext_missing_fields()
            if not self.nfse10_cPaisResult:
                missing.append("nfse10_cPaisResult")
            if missing:
                errors.append(
                    _(
                        "Line %(line)s is an export of service (issqn_eligibility "
                        "'4') and is missing: %(fields)s.",
                        line=self.display_name,
                        fields=", ".join(missing),
                    )
                )
        if self.issqn_eligibility in ("6", "7") and not self.nfse10_nProcesso:
            errors.append(
                _(
                    "Line %(line)s has a suspended ISSQN liability and is "
                    "missing nfse10_nProcesso.",
                    line=self.display_name,
                )
            )
        if self.issqn_eligibility == "3":
            missing = []
            if not self.nfse10_nBM:
                missing.append("nfse10_nBM")
            if not (self.nfse10_vRedBCBM or self.nfse10_pRedBCBM):
                missing.append("nfse10_vRedBCBM or nfse10_pRedBCBM")
            if missing:
                errors.append(
                    _(
                        "Line %(line)s is an ISSQN exemption and is missing: "
                        "%(fields)s.",
                        line=self.display_name,
                        fields=", ".join(missing),
                    )
                )
        return errors

    def _export_many2one(self, field_name, xsd_required, class_obj=None):
        internal_stack_mappings = [
            "nfse10_locPrest",
            "nfse10_cServ",
            "nfse10_vServPrest",
            "nfse10_vDescCondIncond",
            "nfse10_trib",
            "nfse10_tribMun",
            "nfse10_exigSusp",
            "nfse10_BM",
            "nfse10_comExt",
            "nfse10_tribFed",
            "nfse10_piscofins",
            "nfse10_totTrib",
            "nfse10_vTotTrib",
            "nfse10_pTotTrib",
        ]
        if field_name in internal_stack_mappings:
            return self._build_binding(
                class_name=class_obj._fields[field_name].comodel_name,
                field_name=field_name,
            )
        return super()._export_many2one(field_name, xsd_required, class_obj)
