# Copyright 2023 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
import re
import string

from erpbrasil.assinatura import certificado as cert
from erpbrasil.transmissao import TransmissaoSOAP
from nfelib.cte.bindings.v4_0.cte_v4_00 import Cte
from requests import Session

from odoo import _, api, fields
from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal.constants.fiscal import EVENT_ENV_HML, EVENT_ENV_PROD
from odoo.addons.spec_driven_model.models import spec_models

_logger = logging.getLogger(__name__)
try:
    pass
except ImportError:
    _logger.error("Biblioteca erpbrasil.base não instalada")


def filter_processador_edoc_cte(record):
    if record.processador_edoc == "oca" and record.document_type_id.code in [
        "57",
        "67",
    ]:
        return True
    return False


class CTe(spec_models.StackedModel):

    _name = "l10n_br_fiscal.document"
    _inherit = ["l10n_br_fiscal.document", "cte.40.tcte_infcte", "cte.40.tcte_fat"]
    _stacked = "cte.40.tcte_infcte"
    _field_prefix = "cte40_"
    _schema_name = "cte"
    _schema_version = "4.0.0"
    _odoo_module = "l10n_br_cte"
    _spec_module = "odoo.addons.l10n_br_cte_spec.models.v4_0.cte_tipos_basico_v4_00"
    _binding_module = "nfelib.cte.bindings.v4_0.cte_v4_00"
    _cte_search_keys = ["cte40_Id"]

    INFCTE_TREE = """
    > infCte
        > <ide>
        - <toma> res.partner
        > <emit> res.company
        > <dest> res.partner
        > <vPrest>
        > <imp>
        - <ICMS>
        - <ICMSUFFim>
        > <infCTeNorm>
        - <infCarga>
        - <infModal>"""

    ##########################
    # CT-e spec related fields
    ##########################

    ##########################
    # CT-e tag: infCte
    ##########################

    cte40_versao = fields.Char(related="document_version")

    cte40_Id = fields.Char(
        compute="_compute_cte40_Id",
        inverse="_inverse_cte40_Id",
    )

    ##########################
    # CT-e tag: Id
    # Methods
    ##########################

    @api.depends("document_type_id", "document_key")
    def _compute_cte40_Id(self):
        for record in self.filtered(filter_processador_edoc_cte):
            if (
                record.document_type_id
                and record.document_type_id.prefix
                and record.document_key
            ):
                record.cte40_Id = "{}{}".format(
                    record.document_type_id.prefix, record.document_key
                )
            else:
                record.cte40_Id = False

    def _inverse_cte40_Id(self):
        for record in self:
            if record.cte40_Id:
                record.document_key = re.findall(r"\d+", str(record.cte40_Id))[0]

    ##########################
    # CT-e tag: ide
    ##########################

    cte40_cUF = fields.Char(
        related="company_id.partner_id.state_id.ibge_code",
        string="cte40_cUF",
    )

    cte40_cCT = fields.Char(related="document_key")

    cfop_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.cfop",
        string="CFOP",
    )

    cte40_CFOP = fields.Char(related="cfop_id.code")

    cte40_natOp = fields.Char(related="operation_name")

    cte40_mod = fields.Char(related="document_type_id.code", string="cte40_mod")

    cte40_serie = fields.Char(related="document_serie")

    cte40_nCT = fields.Char(related="document_number")

    cte40_dhEmi = fields.Datetime(related="document_date")

    cte40_cDV = fields.Char(compute="_compute_cDV", store=True)

    cte40_procEmi = fields.Selection(default="0")

    cte40_verProc = fields.Char(
        copy=False,
        default=lambda s: s.env["ir.config_parameter"]
        .sudo()
        .get_param("l10n_br_cte.version.name", default="Odoo Brasil OCA v14"),
    )

    cte40_cMunEnv = fields.Char(compute="_compute_cte40_data", store=True)

    cte40_xMunEnv = fields.Char(compute="_compute_cte40_data", store=True)

    cte40_UFEnv = fields.Char(
        compute="_compute_cte40_data", string="cte40_UFEnv", store=True
    )

    cte40_indIEToma = fields.Char(compute="_compute_toma", store=True)

    cte40_cMunIni = fields.Char(compute="_compute_cte40_data", store=True)

    cte40_xMunIni = fields.Char(compute="_compute_cte40_data", store=True)

    cte40_UFIni = fields.Char(compute="_compute_cte40_data", store=True)

    cte40_cMunFim = fields.Char(
        compute="_compute_cte40_data",
        related="partner_id.city_id.ibge_code",
        store=True,
    )

    cte40_xMunFim = fields.Char(
        compute="_compute_cte40_data", related="partner_id.city_id.name", store=True
    )

    cte40_UFFim = fields.Char(
        compute="_compute_cte40_data", string="cte40_cUF", store=True
    )

    cte40_retira = fields.Selection(selection=[("0", "Sim"), ("1", "Não")], default="1")

    cte40_tpServ = fields.Selection(
        selection=[
            ("6", "Transporte de Pessoas"),
            ("7", "Transporte de Valores"),
            ("8", "Excesso de Bagagem"),
        ],
        default="6",
    )

    cte40_tpCTe = fields.Selection(
        selection=[
            ("0", "CTe Normal"),
            ("1", "CTe Complementar"),
            ("3", "CTe Substituição"),
        ],
        default="0",
    )

    cte40_tpAmb = fields.Selection(
        selection=[("1", "Produção"), ("2", "Homologação")],
        string="CTe Environment",
        copy=False,
        default="2",
    )

    cte40_tpEmis = fields.Selection(
        selection=[
            ("1", "Normal"),
            ("3", "Regime Especial NFF"),
            ("4", "EPEC pela SVC"),
        ],
        default="1",
    )

    cte40_tpImp = fields.Selection(
        selection=[("1", "Retrato"), ("2", "Paisagem")], default="1"
    )

    cte40_toma4 = fields.Many2one(
        comodel_name="res.partner",
        compute="_compute_toma",
        readonly=True,
        string="Tomador de Serviço",
    )

    cte40_toma3 = fields.Many2one(
        comodel_name="res.partner",
        compute="_compute_toma",
        readonly=True,
        string="Tomador de Serviço",
    )

    ##########################
    # CT-e tag: ide
    # Compute Methods
    ##########################

    def _compute_toma(self):
        for doc in self:
            if doc.service_provider in ["0", "1"]:
                doc.cte40_toma3 = doc.company_id
                doc.cte40_indIEToma = doc.cte40_toma3.inscr_est
                doc.cte40_toma4 = None
            elif doc.service_provider in ["2", "3"]:
                doc.cte40_toma3 = doc.partner_id
                doc.cte40_indIEToma = doc.cte40_toma3.inscr_est
                doc.cte40_toma4 = None
            else:
                doc.cte40_toma3 = None
                doc.cte40_toma4 = doc.partner_id
                doc.cte40_indIEToma = doc.cte40_toma4.inscr_est

    def _compute_cDV(self):
        for rec in self:
            if rec.document_key:
                rec.cte40_cDV = rec.document_key[:-1]

    @api.depends("partner_id", "company_id")
    def _compute_cte40_data(self):
        for doc in self:
            if doc.company_id.partner_id.country_id == doc.partner_id.country_id:
                doc.cte40_xMunIni = doc.company_id.partner_id.city_id.name
                doc.cte40_cMunIni = doc.company_id.partner_id.city_id.ibge_code
                doc.cte40_xMunEnv = doc.company_id.partner_id.city_id.name
                doc.cte40_cMunEnv = doc.company_id.partner_id.city_id.ibge_code
                doc.cte40_UFEnv = doc.company_id.partner_id.state_id.code
                doc.cte40_UFIni = doc.company_id.partner_id.state_id.ibge_code
                doc.cte40_cMunFim = doc.partner_id.city_id.ibge_code
                doc.cte40_xMunFim = doc.partner_id.city_id.name
                doc.cte40_UFFim = doc.partner_id.state_id.code
            else:
                doc.cte40_UFIni = "EX"
                doc.cte40_UFEnv = "EX"
                doc.cte40_xMunIni = "EXTERIOR"
                doc.cte40_cMunIni = "9999999"
                doc.cte40_xMunEnv = (
                    doc.company_id.partner_id.country_id.name
                    + "/"
                    + doc.company_id.partner_id.city_id.name
                )
                doc.cte40_cMunEnv = "9999999"
                doc.cte40_cMunFim = "9999999"
                doc.cte40_xMunFim = "EXTERIOR"
                doc.cte40_UFFim = "EX"

    ##########################
    # CT-e tag: emit
    ##########################

    cte40_emit = fields.Many2one(
        comodel_name="res.company",
        compute="_compute_emit_data",
        readonly=True,
        string="Emit",
    )

    cte40_CRT = fields.Selection(
        related="company_tax_framework",
        string="Código de Regime Tributário (NFe)",
    )

    ##########################
    # CT-e tag: emit
    # Compute Methods
    ##########################

    def _compute_emit_data(self):
        for doc in self:  # TODO if out
            doc.cte40_emit = doc.company_id

    ##########################
    # CT-e tag: rem
    ##########################

    cte40_rem = fields.Many2one(
        comodel_name="res.company",
        compute="_compute_rem_data",
        readonly=True,
        string="Rem",
        store=True,
    )

    ##########################
    # CT-e tag: rem
    # Compute Methods
    ##########################

    def _compute_rem_data(self):
        for doc in self:  # TODO if out
            doc.cte40_rem = doc.company_id

    ##########################
    # CT-e tag: exped
    ##########################

    cte40_exped = fields.Many2one(
        comodel_name="res.company",
        compute="_compute_exped_data",
        readonly=True,
        string="Exped",
        store=True,
    )

    ##########################
    # CT-e tag: exped
    # Compute Methods
    ##########################

    def _compute_exped_data(self):
        for doc in self:  # TODO if out
            doc.cte40_exped = doc.company_id

    ##########################
    # CT-e tag: receb
    ##########################

    cte40_receb = fields.Many2one(
        comodel_name="res.company",
        compute="_compute_receb_data",
        readonly=True,
        string="Receb",
        store=True,
    )

    ##########################
    # CT-e tag: receb
    # Compute Methods
    ##########################

    def _compute_receb_data(self):
        for doc in self:  # TODO if out
            doc.cte40_receb = doc.company_id

    ##########################
    # CT-e tag: dest
    ##########################

    cte40_dest = fields.Many2one(
        comodel_name="res.partner",
        compute="_compute_dest_data",
        readonly=True,
        string="Dest",
        store=True,
    )

    ##########################
    # CT-e tag: dest
    # Compute Methods
    ##########################

    def _compute_dest_data(self):
        for doc in self:  # TODO if out
            doc.cte40_dest = doc.partner_id

    ##########################
    # CT-e tag: imp
    ##########################

    cte40_imp = fields.One2many(related="fiscal_line_ids")

    #####################################
    # CT-e tag: infCTeNorm and infCteComp
    #####################################

    cte40_choice_infcteNorm_infcteComp = fields.Selection(
        selection=[
            ("cte40_infCTeComp", "infCTeComp"),
            ("cte40_infCTeNorm", "infCTeNorm"),
        ],
        default="cte40_infCTeNorm",
    )

    cte40_infCarga = fields.One2many(
        comodel_name="l10n_br_fiscal.document.related",
        string="Informações de quantidades da Carga do CTe",
        inverse_name="document_id",
    )

    cte40_infCTeNorm = fields.One2many(
        comodel_name="l10n_br_fiscal.document.related",
        inverse_name="document_id",
    )

    cte40_infCTeComp = fields.One2many(
        comodel_name="l10n_br_fiscal.document.related",
        inverse_name="document_id",
    )

    ##########################
    # CT-e tag: autXML
    # Compute Methods
    ##########################

    def _default_cte40_autxml(self):
        company = self.env.company
        authorized_partners = []
        if company.accountant_id and company.cte_authorize_accountant_download_xml:
            authorized_partners.append(company.accountant_id.id)
        if (
            company.technical_support_id
            and company.cte_authorize_technical_download_xml
        ):
            authorized_partners.append(company.technical_support_id.id)
        return authorized_partners

    ##########################
    # CT-e tag: autXML
    ##########################

    cte40_autXML = fields.One2many(default=_default_cte40_autxml)

    ##########################
    # CT-e tag: modal
    ##########################

    cte40_modal = fields.Selection(related="transport_modal")

    cte40_infModal = fields.Many2one(compute="_compute_modal")

    ##########################
    # CT-e tag: modal
    # Compute Methods
    ##########################

    def _compute_modal(self):
        if self.cte40_modal == "1":
            self.cte40_infModal = self.cte40_rodoviario
        elif self.cte40_modal == "2":
            self.cte40_infModal = self.cte40_aereo
        elif self.cte40_modal == "3":
            self.cte40_infModal = self.cte40_aquav
        elif self.cte40_modal == "4":
            self.cte40_infModal = self.cte40_ferroviario
        elif self.cte40_modal == "5":
            self.cte40_infModal = self.cte40_dutoviario
        elif self.cte40_modal == "6":
            pass  # TODO

    cte40_aquav = fields.Many2one(
        comodel_name="l10n_br_cte.aquaviario", inverse_name="document_id"
    )

    cte40_dutoviario = fields.Many2one(
        comodel_name="l10n_br_cte.dutoviario", inverse_name="document_id"
    )

    cte40_rodoviario = fields.Many2one(
        comodel_name="l10n_br_cte.rodoviario", inverse_name="document_id"
    )

    cte40_ferroviario = fields.Many2one(
        comodel_name="l10n_br_cte.ferroviario", inverse_name="document_id"
    )

    cte40_aereo = fields.Many2one(
        comodel_name="l10n_br_cte.aereo", inverse_name="document_id"
    )

    ################################
    # Business Model Methods
    ################################

    def _serialize(self, edocs):
        edocs = super()._serialize(edocs)
        for record in self.with_context(lang="pt_BR").filtered(
            filter_processador_edoc_cte
        ):
            inf_cte = record.export_ds()[0]
            cte = Cte(infCte=inf_cte, infCTeSupl=None, signature=None)
            edocs.append(cte)
        return edocs

    def _processador(self):
        if not self.company_id.certificate_nfe_id:
            raise UserError(_("Certificado não encontrado"))

        certificado = cert.Certificado(
            arquivo=self.company_id.certificate_nfe_id.file,
            senha=self.company_id.certificate_nfe_id.password,
        )
        session = Session()
        session.verify = False
        transmissao = TransmissaoSOAP(certificado, session)
        return Cte(
            transmissao,
            self.company_id.state_id.ibge_code,
            # versao=self.cte40_versao,
            # ambiente=self.cte40_tpAmb,
        )

    # def _document_export(self, pretty_print=True):
    #     result = super()._document_export()
    #     for record in self.filtered(filter_processador_edoc_cte):
    #         edoc = record.serialize()[0]
    #         record._processador()
    #         xml_file = edoc.to_xml()
    #         event_id = self.event_ids.create_event_save_xml(
    #             company_id=self.company_id,
    #             environment=(
    #                 EVENT_ENV_PROD if self.cte40_tpAmb == "1" else EVENT_ENV_HML
    #             ),
    #             event_type="0",
    #             xml_file=xml_file,
    #             document_id=self,
    #         )
    #         record.authorization_event_id = event_id
    #         # xml_assinado = processador.assinar_edoc(edoc, edoc.infCte.Id)
    #         # self._valida_xml(xml_assinado)
    #     return result

    def _document_export(self, pretty_print=True):
        result = super()._document_export()
        for record in self.filtered(filter_processador_edoc_cte):
            edoc = record.serialize()[0]
            processador = record._processador()
            xml_file = processador.render_edoc_xsdata(edoc, pretty_print=pretty_print)[
                0
            ]
            event_id = self.event_ids.create_event_save_xml(
                company_id=self.company_id,
                environment=(
                    EVENT_ENV_PROD if self.cte40_tpAmb == "1" else EVENT_ENV_HML
                ),
                event_type="0",
                xml_file=xml_file,
                document_id=self,
            )
            record.authorization_event_id = event_id
            # xml_assinado = processador.assina_raiz(edoc, edoc.infNFe.Id)
            # self._valida_xml(xml_assinado)
        return result

    def _valida_xml(self, xml_file):
        self.ensure_one()
        erros = Cte.schema_validation(xml_file)
        erros = "\n".join(erros)
        self.write({"xml_error_message": erros or False})

    def _export_field(self, xsd_field, class_obj, member_spec, export_value=None):
        if xsd_field == "cte40_tpAmb":
            self.env.context = dict(self.env.context)
            self.env.context.update({"tpAmb": self[xsd_field]})
        return super()._export_field(xsd_field, class_obj, member_spec, export_value)

    def _export_many2one(self, field_name, xsd_required, class_obj=None):
        self.ensure_one()
        if field_name in self._stacking_points.keys():
            if (not xsd_required) and field_name not in ["cte40_enderDest"]:
                comodel = self.env[self._stacking_points.get(field_name).comodel_name]
                fields = [
                    f
                    for f in comodel._fields
                    if f.startswith(self._field_prefix) and f in self._fields.keys()
                ]
                sub_tag_read = self.read(fields)[0]
                if not any(
                    v
                    for k, v in sub_tag_read.items()
                    if k.startswith(self._field_prefix)
                ):
                    return False

        return super()._export_many2one(field_name, xsd_required, class_obj)

    def _build_many2one(self, comodel, vals, new_value, key, value, path):
        if key == "cte40_emit" and self.env.context.get("edoc_type") == "in":
            enderEmit_value = self.env["res.partner"].build_attrs(
                value.enderEmit, path=path
            )
            new_value.update(enderEmit_value)
            company_cnpj = self.env.user.company_id.cnpj_cpf.translate(
                str.maketrans("", "", string.punctuation)
            )
            emit_cnpj = new_value.get("cte40_CNPJ").translate(
                str.maketrans("", "", string.punctuation)
            )
            if company_cnpj != emit_cnpj:
                vals["issuer"] = "partner"
            new_value["is_company"] = True
            new_value["cnpj_cpf"] = emit_cnpj
            super()._build_many2one(
                self.env["res.partner"], vals, new_value, "partner_id", value, path
            )
        elif key == "cte40_entrega" and self.env.context.get("edoc_type") == "in":
            enderEntreg_value = self.env["res.partner"].build_attrs(value, path=path)
            new_value.update(enderEntreg_value)
            parent_domain = [("cte40_CNPJ", "=", new_value.get("cte40_CNPJ"))]
            parent_partner_match = self.env["res.partner"].search(
                parent_domain, limit=1
            )
            new_vals = {
                "cte40_CNPJ": False,
                "type": "delivery",
                "parent_id": parent_partner_match.id,
                "company_type": "person",
            }
            new_value.update(new_vals)
            super()._build_many2one(
                self.env["res.partner"], vals, new_value, key, value, path
            )
        elif self.env.context.get("edoc_type") == "in" and key in [
            "cte40_dest",
            "cte40_enderDest",
        ]:
            # this would be the emit/company data, but we won't update it on
            # cte import so just do nothing
            return
        elif (
            self._name == "account.invoice"
            and comodel._name == "l10n_br_fiscal.document"
        ):
            # module l10n_br_account_cte
            # stacked m2o
            vals.update(new_value)
        else:
            super()._build_many2one(comodel, vals, new_value, key, value, path)
