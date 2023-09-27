# Copyright 2023 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from erpbrasil.base.misc import punctuation_rm

from odoo import api, fields

from odoo.addons.spec_driven_model.models import spec_models


class MDFeModalRodoviario(spec_models.StackedModel):
    _name = "l10n_br_mdfe.modal.rodoviario"
    _inherit = "mdfe.30.rodo"
    _stacked = "mdfe.30.rodo"
    _binding_module = "nfelib.mdfe.bindings.v3_0.mdfe_modal_rodoviario_v3_00"
    _field_prefix = "mdfe30_"
    _schema_name = "mdfe"
    _schema_version = "3.0.0"
    _odoo_module = "l10n_br_mdfe"
    _spec_module = (
        "odoo.addons.l10n_br_mdfe_spec.models.v3_0.mdfe_modal_rodoviario_v3_00"
    )
    _spec_tab_name = "MDFe"
    _description = "Modal Rodoviário MDFe"

    # all m2o at this level will be stacked even if not required:
    _force_stack_paths = [
        "rodo.infantt.valeped",
    ]

    document_id = fields.Many2one(comodel_name="l10n_br_fiscal.document")

    mdfe30_codAgPorto = fields.Char(related="document_id.rodo_scheduling_code")

    mdfe30_infCIOT = fields.One2many(related="document_id.rodo_ciot_ids")

    mdfe30_disp = fields.One2many(related="document_id.rodo_toll_device_ids")

    mdfe30_categCombVeic = fields.Selection(
        related="document_id.rod_toll_vehicle_categ"
    )

    mdfe30_infContratante = fields.One2many(compute="_compute_contractor")

    mdfe30_RNTRC = fields.Char(related="document_id.rodo_RNTRC")

    mdfe30_infPag = fields.One2many(related="document_id.rodo_payment_ids")

    mdfe30_prop = fields.Many2one(related="document_id.rodo_vehicle_proprietary_id")

    mdfe30_condutor = fields.One2many(related="document_id.rodo_vehicle_conductor_ids")

    mdfe30_cInt = fields.Char(related="document_id.rodo_vehicle_code")

    mdfe30_RENAVAM = fields.Char(related="document_id.rodo_vehicle_RENAVAM")

    mdfe30_placa = fields.Char(related="document_id.rodo_vehicle_plate")

    mdfe30_tara = fields.Char(related="document_id.rodo_vehicle_tare_weight")

    mdfe30_capKG = fields.Char(related="document_id.rodo_vehicle_kg_capacity")

    mdfe30_capM3 = fields.Char(related="document_id.rodo_vehicle_m3_capacity")

    mdfe30_tpRod = fields.Selection(related="document_id.rodo_vehicle_tire_type")

    mdfe30_tpCar = fields.Selection(related="document_id.rodo_vehicle_type")

    mdfe30_UF = fields.Selection(compute="_compute_uf")

    mdfe30_veicReboque = fields.One2many(related="document_id.rodo_tow_ids")

    mdfe30_lacRodo = fields.One2many(related="document_id.rodo_seal_ids")

    @api.depends("document_id.rodo_vehicle_state_id")
    def _compute_uf(self):
        for record in self:
            record.mdfe30_UF = record.document_id.rodo_vehicle_state_id.code

    @api.depends("document_id.rodo_contractor_ids")
    def _compute_contractor(self):
        for record in self:
            record.mdfe30_infContratante = [
                (6, 0, record.document_id.rodo_contractor_ids.ids)
            ]


class MDFeModalRodoviarioCIOT(spec_models.SpecModel):
    _name = "l10n_br_mdfe.modal.rodoviario.ciot"
    _inherit = "mdfe.30.infciot"
    _binding_module = "nfelib.mdfe.bindings.v3_0.mdfe_modal_rodoviario_v3_00"
    _mdfe_search_keys = ["mdfe30_CIOT"]
    _description = "Informações do CIOT no Modal Rodoviário MDFe"

    document_id = fields.Many2one(comodel_name="l10n_br_fiscal.document")

    mdfe30_CIOT = fields.Char(required=True, size=12)

    is_company = fields.Boolean(string="É empresa?", required=True)

    mdfe30_CNPJ = fields.Char(string="CNPJ do responsável")

    mdfe30_CPF = fields.Char(string="CPF do responsável")

    mdfe30_choice1 = fields.Selection(
        selection=[("mdfe30_CNPJ", "CNPJ"), ("mdfe30_CPF", "CPF")],
        string="CNPJ/CPF do responsável",
        compute="_compute_ciot_choice",
    )

    @api.depends("is_company")
    def _compute_ciot_choice(self):
        for record in self:
            record.mdfe30_choice1 = "mdfe30_CNPJ" if record.is_company else "mdfe30_CPF"


class MDFeModalRodoviarioValePedagioDispositivo(spec_models.SpecModel):
    _name = "l10n_br_mdfe.modal.rodoviario.vale_pedagio.dispositivo"
    _inherit = "mdfe.30.disp"
    _binding_module = "nfelib.mdfe.bindings.v3_0.mdfe_modal_rodoviario_v3_00"
    _description = "Informações de Dispositivos do Pedágio no Modal Rodoviário MDFe"

    document_id = fields.Many2one(comodel_name="l10n_br_fiscal.document")

    mdfe30_CNPJForn = fields.Char(required=True)

    mdfe30_vValePed = fields.Monetary(required=True)


class MDFeModalRodoviarioPagamento(spec_models.SpecModel):
    _name = "l10n_br_mdfe.modal.rodoviario.pagamento"
    _inherit = "mdfe.30.rodo_infpag"
    _binding_module = "nfelib.mdfe.bindings.v3_0.mdfe_modal_rodoviario_v3_00"
    _description = "Informações do Pagamento do Modal Rodoviário MDFe"

    document_id = fields.Many2one(comodel_name="l10n_br_fiscal.document")

    partner_id = fields.Many2one(
        comodel_name="res.partner", string="Responsável pelo pagamento", required=True
    )

    mdfe30_CNPJ = fields.Char(related="partner_id.mdfe30_CNPJ")

    mdfe30_CPF = fields.Char(related="partner_id.mdfe30_CPF")

    mdfe30_xNome = fields.Char(related="partner_id.mdfe30_xNome")

    mdfe30_choice1 = fields.Selection(
        selection=[
            ("mdfe30_CNPJ", "CNPJ"),
            ("mdfe30_CPF", "CPF"),
            ("mdfe40_idEstrangeiro", "idEstrangeiro"),
        ],
        string="CNPJ/CPF/Id Estrangeiro do responsável pelo pagamento",
        compute="_compute_mdfe_data",
    )

    mdfe30_comp = fields.One2many(
        comodel_name="l10n_br_mdfe.modal.rodoviario.pagamento.frete"
    )

    mdfe30_infPrazo = fields.One2many(
        comodel_name="l10n_br_mdfe.modal.rodoviario.pagamento.prazo"
    )

    mdfe30_vContrato = fields.Monetary(required=True)

    mdfe30_indPag = fields.Selection(required=True)

    mdfe30_infBanc = fields.Many2one(
        comodel_name="l10n_br_mdfe.modal.rodoviario.pagamento.banco", required=True
    )

    @api.depends("partner_id")
    def _compute_mdfe_data(self):
        for rec in self:
            cnpj_cpf = punctuation_rm(rec.partner_id.cnpj_cpf)
            if cnpj_cpf:
                if rec.partner_id.country_id.code != "BR":
                    rec.mdfe30_choice1 = "mdfe40_idEstrangeiro"
                elif rec.partner_id.is_company:
                    rec.mdfe30_choice1 = "mdfe30_CNPJ"
                else:
                    rec.mdfe30_choice1 = "mdfe30_CPF"
            else:
                rec.mdfe30_choice1 = False


class MDFeModalRodoviarioPagamentoBanco(spec_models.SpecModel):
    _name = "l10n_br_mdfe.modal.rodoviario.pagamento.banco"
    _inherit = "mdfe.30.rodo_infbanc"
    _binding_module = "nfelib.mdfe.bindings.v3_0.mdfe_modal_rodoviario_v3_00"
    _description = "Informações de Pagamento Bancário no Modal Rodoviário MDFe"

    payment_type = fields.Selection(
        selection=[
            ("bank", "Banco"),
            ("pix", "PIX"),
        ],
        string="Meio de Pagamento",
        default="bank",
    )

    mdfe30_choice1 = fields.Selection(
        selection=[
            ("mdfe30_codBanco", "Banco"),
            ("mdfe30_codAgencia", "Agencia"),
            ("mdfe30_CNPJIPEF", "CNPJ"),
            ("mdfe30_PIX", "PIX"),
        ],
        string="Método de Pagamento",
        compute="_compute_payment_type",
    )

    @api.depends("payment_type")
    def _compute_payment_type(self):
        for record in self:
            if record.payment_type == "bank":
                record.mdfe30_choice1 = "mdfe30_codBanco"
            elif record.payment_type == "pix":
                record.mdfe30_choice1 = "mdfe30_PIX"
            else:
                record.mdfe30_choice1 = False


class MDFeModalRodoviarioPagamentoFrete(spec_models.SpecModel):
    _name = "l10n_br_mdfe.modal.rodoviario.pagamento.frete"
    _inherit = "mdfe.30.rodo_comp"
    _binding_module = "nfelib.mdfe.bindings.v3_0.mdfe_modal_rodoviario_v3_00"
    _description = "Informações do Frete no Pagamento do Modal Rodoviário MDFe"

    mdfe30_tpComp = fields.Selection(required=True)

    mdfe30_vComp = fields.Monetary(required=True)


class MDFeModalRodoviarioPagamentoPrazo(spec_models.SpecModel):
    _name = "l10n_br_mdfe.modal.rodoviario.pagamento.prazo"
    _inherit = "mdfe.30.rodo_infprazo"
    _binding_module = "nfelib.mdfe.bindings.v3_0.mdfe_modal_rodoviario_v3_00"
    _description = "Informações de Prazo de Pagamento do Modal Rodoviário MDFe"

    mdfe30_nParcela = fields.Char(required=True)

    mdfe30_dVenc = fields.Date(required=True)

    mdfe30_vParcela = fields.Monetary(required=True)


class MDFeModalRodoviarioVeiculoCondutor(spec_models.SpecModel):
    _name = "l10n_br_mdfe.modal.rodoviario.veiculo.condutor"
    _inherit = "mdfe.30.rodo_condutor"
    _binding_module = "nfelib.mdfe.bindings.v3_0.mdfe_modal_rodoviario_v3_00"
    _description = "Informações do Condutor no Modal Rodoviário MDFe"

    document_id = fields.Many2one(comodel_name="l10n_br_fiscal.document")

    mdfe30_xNome = fields.Char(required=True)

    mdfe30_CPF = fields.Char(required=True)


class MDFeModalRodoviarioReboque(spec_models.SpecModel):
    _name = "l10n_br_mdfe.modal.rodoviario.reboque"
    _inherit = "mdfe.30.veicreboque"
    _binding_module = "nfelib.mdfe.bindings.v3_0.mdfe_modal_rodoviario_v3_00"
    _description = "Informações de Reboque no Modal Rodoviário MDFe"

    document_id = fields.Many2one(comodel_name="l10n_br_fiscal.document")

    mdfe30_prop = fields.Many2one(comodel_name="res.partner")

    mdfe30_placa = fields.Char(required=True)

    mdfe30_tara = fields.Char(required=True)

    mdfe30_capKG = fields.Char(required=True)

    mdfe30_tpCar = fields.Selection(required=True)

    mdfe30_cInt = fields.Char(size=10)

    mdfe30_RENAVAM = fields.Char(size=11)
