# Copyright 2023 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re
from unicodedata import normalize

from nfelib.mdfe.bindings.v3_0.mdfe_modal_aereo_v3_00 import Aereo
from nfelib.mdfe.bindings.v3_0.mdfe_modal_aquaviario_v3_00 import Aquav
from nfelib.mdfe.bindings.v3_0.mdfe_modal_ferroviario_v3_00 import Ferrov
from nfelib.mdfe.bindings.v3_0.mdfe_modal_rodoviario_v3_00 import Rodo
from nfelib.mdfe.bindings.v3_0.mdfe_v3_00 import Mdfe
from nfelib.nfe.ws.edoc_legacy import MDFeAdapter as edoc_mdfe

from odoo import api, fields

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    EVENT_ENV_HML,
    EVENT_ENV_PROD,
    MODELO_FISCAL_MDFE,
    PROCESSADOR_OCA,
)
from odoo.addons.l10n_br_mdfe_spec.models.v3_0.mdfe_modal_aquaviario_v3_00 import (
    AQUAV_TPNAV,
)
from odoo.addons.l10n_br_mdfe_spec.models.v3_0.mdfe_modal_rodoviario_v3_00 import (
    VALEPED_CATEGCOMBVEIC,
    VEICTRACAO_TPCAR,
    VEICTRACAO_TPROD,
)
from odoo.addons.spec_driven_model.models import spec_models

from ..constants.mdfe import (
    MDFE_EMISSION_PROCESS_DEFAULT,
    MDFE_EMISSION_PROCESSES,
    MDFE_EMIT_TYPES,
    MDFE_ENVIRONMENTS,
    MDFE_TRANSMISSIONS,
    MDFE_TRANSP_TYPE,
)
from ..constants.modal import (
    MDFE_MODAL_DEFAULT,
    MDFE_MODAL_DEFAULT_AIRCRAFT,
    MDFE_MODAL_HARBORS,
    MDFE_MODAL_SHIP_TYPES,
    MDFE_MODALS,
)


def filtered_processador_edoc_mdfe(record):
    return (
        record.processador_edoc == PROCESSADOR_OCA
        and record.document_type_id.code == MODELO_FISCAL_MDFE
    )


class MDFe(spec_models.StackedModel):

    _name = "l10n_br_fiscal.document"
    _inherit = ["l10n_br_fiscal.document", "mdfe.30.tmdfe_infmdfe"]
    _stacked = "mdfe.30.tmdfe_infmdfe"
    _field_prefix = "mdfe30_"
    _schame_name = "mdfe"
    _schema_version = "3.0.0"
    _odoo_module = "l10n_br_mdfe"
    _spec_module = "odoo.addons.l10n_br_mdfe_spec.models.v3_0.mdfe_tipos_basico_v3_00"
    _spec_tab_name = "MDFe"
    _mdfe_search_keys = ["mdfe30_Id"]

    # all m2o at this level will be stacked even if not required:
    _force_stack_paths = "infmdfe.infAdic"

    INFMDFE_TREE = """
    > <infMDFe>
        > <ide>
        - <emit> res.company
        - <infModal>
        - <infDoc> l10n_br_fiscal.document.related
        > <tot>
    """

    ##########################
    # MDF-e spec related fields
    ##########################

    ##########################
    # MDF-e tag: infMDFe
    ##########################

    mdfe30_versao = fields.Char(related="document_version")

    mdfe30_Id = fields.Char(
        compute="_compute_mdfe30_id_tag",
        inverse="_inverse_mdfe30_id_tag",
    )

    ##########################
    # MDF-e tag: infMDFe
    # Methods
    ##########################

    @api.depends("document_type_id", "document_key")
    def _compute_mdfe30_id_tag(self):
        """Set schema data which are not just related fields"""

        for record in self.filtered(filtered_processador_edoc_mdfe):
            if (
                record.document_type_id
                and record.document_type.prefix
                and record.document_key
            ):
                record.mdfe30_Id = "{}{}".format(
                    record.document_type.prefix, record.document_key
                )
            else:
                record.mdfe30_Id = False

    def _inverse_mdfe30_id_tag(self):
        for record in self:
            if record.mdfe30_Id:
                record.document_key = re.findall(r"\d+", str(record.mdfe30_Id))[0]

    ##########################
    # MDF-e tag: ide
    ##########################

    mdfe30_cUF = fields.Selection(compute="_compute_uf")

    mdfe30_tpAmb = fields.Selection(related="mdfe_environment")

    mdfe_environment = fields.Selection(
        selection=MDFE_ENVIRONMENTS,
        string="Environment",
        copy=False,
        default=lambda self: self.env.company.mdfe_environment,
    )

    mdfe30_tpEmit = fields.Selection(related="mdfe_emit_type")

    mdfe_emit_type = fields.Selection(
        selection=MDFE_EMIT_TYPES,
        string="Emit Type",
        copy=False,
        default=lambda self: self.env.company.mdfe_emit_type,
    )

    mdfe30_tpTransp = fields.Selection(related="mdfe_transp_type")

    mdfe_transp_type = fields.Selection(
        selection=MDFE_TRANSP_TYPE,
        string="Transp Type",
        copy=False,
        default=lambda self: self.env.company.mdfe_transp_type,
    )

    mdfe30_mod = fields.Char(related="document_type_id.code")

    mdfe30_serie = fields.Char(related="document_serie")

    mdfe30_nMDF = fields.Char(related="document_number")

    mdfe30_dhEmi = fields.Datetime(related="document_date")

    mdfe30_modal = fields.Selection(related="mdfe_modal")

    mdfe_modal = fields.Selection(
        selection=MDFE_MODALS, string="Transport Modal", default=MDFE_MODAL_DEFAULT
    )

    mdfe30_tpEmis = fields.Selection(related="mdfe_transmission")

    mdfe_transmission = fields.Selection(
        selection=MDFE_TRANSMISSIONS,
        string="Transmission",
        copy=False,
        default=lambda self: self.env.company.mdfe_transmission,
    )

    mdfe30_procEmi = fields.Selection(
        selection=MDFE_EMISSION_PROCESSES,
        string="Emission Process",
        default=MDFE_EMISSION_PROCESS_DEFAULT,
    )

    mdfe30_verProc = fields.Char(
        copy=False,
        default=lambda s: s.env["ir.config_parameter"]
        .sudo()
        .get_param("l10n_br_mdfe.version.name", default="Odoo Brasil OCA v14"),
    )

    mdfe30_UFIni = fields.Selection(compute="_compute_initial_final_state")

    mdfe30_UFFim = fields.Selection(compute="_compute_initial_final_state")

    mdfe_initial_state_id = fields.Many2one(
        comodel_name="res.country.state",
        string="Initial State",
        domain=[("country_id.code", "=", "BR")],
    )

    mdfe_final_state_id = fields.Many2one(
        comodel_name="res.country.state",
        string="Final State",
        domain=[("country_id.code", "=", "BR")],
    )

    mdfe30_cMDF = fields.Char(related="key_random_code")

    mdfe30_cDV = fields.Char(related="key_check_digit")

    mdfe30_infMunCarrega = fields.One2many(compute="_compute_inf_carrega")

    mdfe_loading_city_ids = fields.Many2many(
        comodel_name="res.city", string="Loading Cities"
    )

    mdfe30_infPercurso = fields.One2many(compute="_compute_inf_percurso")

    mdfe_route_state_ids = fields.Many2many(
        comodel_name="res.country.state",
        string="Route States",
        domain=[("country_id.code", "=", "BR")],
    )

    ##########################
    # MDF-e tag: ide
    # Methods
    ##########################

    @api.depends("company_id")
    def _compute_uf(self):
        for record in self.filtered(filtered_processador_edoc_mdfe):
            record.mdfe30_cUF = record.company_id.partner_id.state_id.ibge_code

    @api.depends("mdfe_initial_state_id", "mdfe_final_state_id")
    def _compute_initial_final_state(self):
        for record in self.filtered(filtered_processador_edoc_mdfe):
            record.mdfe30_UFIni = record.mdfe_initial_state_id.code
            record.mdfe30_UFFim = record.mdfe_final_state_id.code

    @api.depends("mdfe_loading_city_ids")
    def _compute_inf_carrega(self):
        for record in self.filtered(filtered_processador_edoc_mdfe):
            record.mdfe30_infMunCarrega = [
                (
                    0,
                    0,
                    {
                        "mdfe30_cMunCarrega": city.ibge_code,
                        "mdfe30_xMunCarrega": city.name,
                    },
                )
                for city in record.mdfe_loading_city_ids
            ]

    @api.depends("mdfe_route_state_ids")
    def _compute_inf_percurso(self):
        for record in self.filtered(filtered_processador_edoc_mdfe):
            record.mdfe30_infPercurso = [
                (
                    0,
                    0,
                    {
                        "mdfe30_UFPer": state.code,
                    },
                )
                for state in record.mdfe_route_state_ids
            ]

    ##########################
    # MDF-e tag: emit
    ##########################

    mdfe30_emit = fields.Many2one(comodel_name="res.company", related="company_id")

    ##########################
    # MDF-e tag: infModal
    ##########################

    mdfe30_infModal = fields.Many2one(
        comodel_name="l10n_br_mdfe.modal",
        string="Modal Info",
        compute="_compute_modal_inf",
    )

    mdfe30_versaoModal = fields.Char(related="mdfe30_infModal.mdfe30_versaoModal")

    # Campos do Modal Aéreo
    airplane_nationality = fields.Char()

    airplane_registration = fields.Char()

    flight_number = fields.Char()

    flight_date = fields.Date()

    boarding_airfield = fields.Char(default=MDFE_MODAL_DEFAULT_AIRCRAFT)

    landing_airfield = fields.Char(default=MDFE_MODAL_DEFAULT_AIRCRAFT)

    # Campos do Modal Aquaviário
    ship_irin = fields.Char()

    ship_type = fields.Selection(selection=MDFE_MODAL_SHIP_TYPES)

    ship_code = fields.Char()

    ship_name = fields.Char()

    ship_travel_number = fields.Char()

    ship_boarding_point = fields.Selection(selection=MDFE_MODAL_HARBORS)

    ship_landing_point = fields.Selection(selection=MDFE_MODAL_HARBORS)

    transshipment_port = fields.Char()

    ship_navigation_type = fields.Selection(selection=AQUAV_TPNAV)

    ship_loading_ids = fields.One2many(
        comodel_name="l10n_br_mdfe.modal.aquaviario.carregamento",
        inverse_name="document_id",
    )

    ship_unloading_ids = fields.One2many(
        comodel_name="l10n_br_mdfe.modal.aquaviario.descarregamento",
        inverse_name="document_id",
    )

    ship_convoy_ids = fields.One2many(
        comodel_name="l10n_br_mdfe.modal.aquaviario.comboio", inverse_name="document_id"
    )

    ship_empty_load_ids = fields.One2many(
        comodel_name="l10n_br_mdfe.modal.aquaviario.carga.vazia",
        inverse_name="document_id",
    )

    ship_empty_transport_ids = fields.One2many(
        comodel_name="l10n_br_mdfe.modal.aquaviario.transporte.vazio",
        inverse_name="document_id",
    )

    # Campos do Modal Ferroviário
    train_prefix = fields.Char(string="Train Prefix")

    train_release_time = fields.Datetime(string="Train Release Time")

    train_origin = fields.Char(string="Train Origin")

    train_destiny = fields.Char(string="Train Destiny")

    train_wagon_quantity = fields.Char(string="Train Wagon Quantity")

    train_wagon_ids = fields.One2many(
        comodel_name="l10n_br_mdfe.modal.ferroviario.vagao", inverse_name="document_id"
    )

    # Campos do Modal Rodoviário
    rodo_scheduling_code = fields.Char(string="Scheduling Code")

    rodo_ciot_ids = fields.One2many(
        comodel_name="l10n_br_mdfe.modal.rodoviario.ciot", inverse_name="document_id"
    )

    rodo_toll_device_ids = fields.One2many(
        comodel_name="l10n_br_mdfe.modal.rodoviario.vale_pedagio.dispositivo",
        inverse_name="document_id",
    )

    rod_toll_vehicle_categ = fields.Selection(selection=VALEPED_CATEGCOMBVEIC)

    rodo_contractor_ids = fields.Many2many(comodel_name="res.partner")

    rodo_RNTRC = fields.Char()

    rodo_payment_ids = fields.One2many(
        comodel_name="l10n_br_mdfe.modal.rodoviario.pagamento",
        inverse_name="document_id",
    )

    rodo_vehicle_proprietary_id = fields.Many2one(comodel_name="res.partner")

    rodo_vehicle_conductor_ids = fields.One2many(
        comodel_name="l10n_br_mdfe.modal.rodoviario.veiculo.condutor",
        inverse_name="document_id",
    )

    rodo_vehicle_code = fields.Char()

    rodo_vehicle_RENAVAM = fields.Char()

    rodo_vehicle_plate = fields.Char()

    rodo_vehicle_tare_weight = fields.Char()

    rodo_vehicle_kg_capacity = fields.Char()

    rodo_vehicle_m3_capacity = fields.Char()

    rodo_vehicle_tire_type = fields.Selection(selection=VEICTRACAO_TPROD)

    rodo_vehicle_type = fields.Selection(selection=VEICTRACAO_TPCAR)

    rodo_vehicle_state_id = fields.Many2one(
        comodel_name="res.country.state",
        string="Vehicle State",
        domain=[("country_id.code", "=", "BR")],
    )

    rodo_tow_ids = fields.One2many(
        comodel_name="l10n_br_mdfe.modal.rodoviario.reboque", inverse_name="document_id"
    )

    rodo_seal_ids = fields.One2many(
        comodel_name="l10n_br_mdfe.modal.rodoviario.lacre", inverse_name="document_id"
    )

    ##########################
    # MDF-e tag: infModal
    # Methods
    ##########################

    @api.depends("mdfe_modal")
    def _compute_modal_inf(self):
        for record in self.filtered(filtered_processador_edoc_mdfe):
            record.mdfe30_infModal = self.env.ref(
                "l10n_br_mdfe.modal_%s" % record.mdfe_modal
            )

    def _export_fields_mdfe_30_infmodal(self, xsd_fields, class_obj, export_dict):
        if self.mdfe_modal == "1":
            export_dict["any_element"] = self._export_modal_rodoviario_fields()
        elif self.mdfe_modal == "2":
            export_dict["any_element"] = self._export_modal_aereo_fields()
        elif self.mdfe_modal == "3":
            export_dict["any_element"] = self._export_modal_aquaviario_fields()
        elif self.mdfe_modal == "4":
            export_dict["any_element"] = self._export_modal_ferroviario_fields()

    def _export_modal_aereo_fields(self):
        return Aereo(
            nac=self.airplane_nationality,
            matr=self.airplane_registration,
            nVoo=self.flight_number,
            dVoo=fields.Date.to_string(self.flight_date),
            cAerEmb=self.boarding_airfield,
            cAerDes=self.landing_airfield,
        )

    def _export_modal_aquaviario_fields(self):
        return Aquav(
            irin=self.ship_irin,
            tpEmb=self.ship_type,
            cEmbar=self.ship_code,
            xEmbar=self.ship_name,
            cPrtEmb=self.ship_boarding_point,
            cPrtDest=self.ship_landing_point,
            prtTrans=self.transshipment_port,
            tpNav=self.ship_navigation_type,
            infTermCarreg=[
                Aquav.InfTermCarreg(**loading.export_fields())
                for loading in self.ship_loading_ids
            ],
            infTermDescarreg=[
                Aquav.InfTermDescarreg(**unloading.export_fields())
                for unloading in self.ship_unloading_ids
            ],
            infEmbComb=[
                Aquav.InfEmbComb(**convoy.export_fields())
                for convoy in self.ship_convoy_ids
            ],
            infUnidCargaVazia=[
                Aquav.infUnidCargaVazia(**load.export_fields())
                for load in self.ship_empty_load_ids
            ],
            infUnidTranspVazia=[
                Aquav.infUnidTranspVazia(**transp.export_fields())
                for transp in self.ship_empty_transport_ids
            ],
        )

    def _export_modal_ferroviario_fields(self):
        return Ferrov(
            trem=Ferrov.Trem(
                xPref=self.train_prefix,
                dhTrem=fields.Datetime.to_string(self.train_release_time),
                xOri=self.train_origin,
                xDest=self.train_destiny,
                qVag=self.train_wagon_quantity,
            ),
            vag=[Ferrov.Vag(**vag.export_fields()) for vag in self.train_wagon_ids],
        )

    def _export_modal_rodoviario_fields(self):
        return Rodo(
            codAgPorto=self.rodo_scheduling_code,
            infANTT=Rodo.infANTT(
                RNTRC=self.rodo_RNTRC,
                infCIOT=self.rodo_ciot_ids.export_fields(),
                valePed=Rodo.InfAntt.ValePed(
                    disp=[
                        Rodo.InfAntt.ValePed.Disp(**dev.export_fields())
                        for dev in self.rodo_toll_device_ids
                    ],
                    categCombVeic=self.rod_toll_vehicle_categ,
                ),
                infContratante=[
                    Rodo.InfAntt.infContratante(**contr.export_contractor_fields())
                    for contr in self.rodo_contractor_ids
                ],
                infPag=[
                    Rodo.InfAntt.infPag(**pay.export_contractor_fields())
                    for pay in self.rodo_payment_ids
                ],
            ),
            lacRodo=[
                Rodo.infANTT.lacRodo(**seal.export_fields())
                for seal in self.rodo_seal_ids
            ],
            veicReboque=[
                Rodo.veicReboque(**tow.export_fields()) for tow in self.rodo_tow_ids
            ],
            veicTracao=Rodo.veicTracao(
                cInt=self.rodo_vehicle_code,
                placa=self.rodo_vehicle_plate,
                RENAVAM=self.rodo_vehicle_RENAVAM,
                tara=self.rodo_vehicle_tare_weight,
                capKG=self.rodo_vehicle_kg_capacity,
                capM3=self.rodo_vehicle_m3_capacity,
                tpRod=self.rodo_vehicle_tire_type,
                tpCar=self.rodo_vehicle_type,
                UF=self.rodo_vehicle_state_id.code,
                condutor=[
                    Rodo.veicTracao.condutor(**cond.export_fields())
                    for cond in self.rodo_vehicle_conductor_ids
                ],
                prop=[
                    Rodo.veicTracao.prop(**prop.export_proprietary_fields())
                    for prop in self.rodo_vehicle_proprietary_id
                ],
            ),
        )

    ##########################
    # MDF-e tag: infDoc
    ##########################

    mdfe30_infDoc = fields.One2many(
        comodel_name="l10n_br_mdfe.document.info", compute="_compute_doc_inf"
    )

    unloading_city_ids = fields.One2many(
        comodel_name="l10n_br_mdfe.municipio.descarga", inverse_name="document_id"
    )

    ##########################
    # MDF-e tag: infDoc
    # Methods
    ##########################

    @api.depends("unloading_city_ids")
    def _compute_doc_inf(self):
        for record in self.filtered(filtered_processador_edoc_mdfe):
            record.mdfe30_infDoc = [(5, 0, 0)]
            record.mdfe30_infDoc = [
                (
                    0,
                    0,
                    {"mdfe30_infMunDescarga": [(6, 0, record.unloading_city_ids.ids)]},
                )
            ]

    ##########################
    # MDF-e tag: infRespTec
    ##########################

    mdfe30_infRespTec = fields.Many2one(
        comodel_name="res.partner",
        related="company_id.technical_support_id",
    )

    ##########################
    # NF-e tag: infAdic
    ##########################

    mdfe30_infAdFisco = fields.Char(compute="_compute_mdfe30_additional_data")

    mdfe30_infCpl = fields.Char(compute="_compute_mdfe30_additional_data")

    ##########################
    # MDF-e tag: infAdic
    # Methods
    ##########################

    @api.depends("fiscal_additional_data")
    def _compute_mdfe30_additional_data(self):
        for record in self:
            record.mdfe30_infCpl = False
            record.mdfe30_infAdFisco = False

            if record.fiscal_additional_data:
                record.mdfe30_infAdFisco = (
                    normalize("NFKD", record.fiscal_additional_data)
                    .encode("ASCII", "ignore")
                    .decode("ASCII")
                    .replace("\n", "")
                    .replace("\r", "")
                )
            if record.customer_additional_data:
                record.mdfe30_infCpl = (
                    normalize("NFKD", record.customer_additional_data)
                    .encode("ASCII", "ignore")
                    .decode("ASCII")
                    .replace("\n", "")
                    .replace("\r", "")
                )

    ##########################
    # MDF-e tag: autXML
    ##########################

    def _default_mdfe30_autxml(self):
        company = self.env.company
        authorized_partners = []
        if company.accountant_id:
            authorized_partners.append(company.accountant_id.id)
        if company.technical_support_id:
            authorized_partners.append(company.technical_support_id.id)
        return authorized_partners

    mdfe30_autXML = fields.One2many(default=_default_mdfe30_autxml)

    ################################
    # Framework Spec model's methods
    ################################

    def _export_field(self, xsd_field, class_obj, member_spec, export_value=None):
        if xsd_field == "mdfe30_tpAmb":
            self.env.context = dict(self.env.context)
            self.env.context.update({"tpAmb": self[xsd_field]})
        return super()._export_field(xsd_field, class_obj, member_spec, export_value)

    def _export_many2one(self, field_name, xsd_required, class_obj=None):
        if field_name == "mdfe30_infModal":
            return self._build_generateds(class_obj._fields[field_name].comodel_name)

        return super()._export_many2one(field_name, xsd_required, class_obj)

    def _build_attr(self, node, fields, vals, path, attr):
        key = "mdfe30_%s" % (attr[0],)  # TODO schema wise
        value = getattr(node, attr[0])

        if key == "mdfe30_mod":
            vals["document_type_id"] = (
                self.env["l10n_br_fiscal.document.type"]
                .search([("code", "=", value)], limit=1)
                .id
            )

        return super()._build_attr(node, fields, vals, path, attr)

    ################################
    # Business Model Methods
    ################################

    def _serialize(self, edocs):
        edocs = super()._serialize(edocs)
        for record in self.with_context(lang="pt_BR").filtered(
            filtered_processador_edoc_mdfe
        ):
            inf_mdfe = record.export_ds()[0]
            mdfe = Mdfe(infMDFe=inf_mdfe, infMDFeSupl=None, signature=None)
            edocs.append(mdfe)
        return edocs

    def _processador(self):
        params = self._prepare_processor_params()
        return edoc_mdfe(**params)

    def _document_export(self, pretty_print=True):
        result = super()._document_export()
        for record in self.filtered(filtered_processador_edoc_mdfe):
            edoc = record.serialize()[0]
            processador = record._processador()
            xml_file = processador.render_edoc_xsdata(edoc, pretty_print=pretty_print)[
                0
            ]
            event_id = self.event_ids.create_event_save_xml(
                company_id=self.company_id,
                environment=(
                    EVENT_ENV_PROD if self.nfe_environment == "1" else EVENT_ENV_HML
                ),
                event_type="0",
                xml_file=xml_file,
                document_id=self,
            )
            record.authorization_event_id = event_id
            xml_assinado = processador.assina_raiz(edoc, edoc.infNFe.Id)
            self._valida_xml(xml_assinado)
        return result

    def _valida_xml(self, xml_file):
        self.ensure_one()
        erros = Mdfe.schema_validation(xml_file)
        erros = "\n".join(erros)
        self.write({"xml_error_message": erros or False})
