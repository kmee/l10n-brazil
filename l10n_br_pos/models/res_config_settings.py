# Copyright 2023 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):

    _inherit = "res.config.settings"

    pos_out_pos_fiscal_operation_id = fields.Many2one(
        related="pos_config_id.out_pos_fiscal_operation_id",
        store=True,
        readonly=False,
    )
    pos_partner_id = fields.Many2one(
        related="pos_config_id.partner_id",
        store=True,
        readonly=False,
    )
    pos_refund_pos_fiscal_operation_id = fields.Many2one(
        related="pos_config_id.refund_pos_fiscal_operation_id",
        store=True,
        readonly=False,
    )
    pos_anonymous_simplified_limit = fields.Float(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )
    pos_simplified_invoice_limit = fields.Float(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )
    pos_simplified_document_type_id = fields.Many2one(
        related="pos_config_id.simplified_document_type_id",
        store=True,
        readonly=False,
    )
    pos_simplified_document_type = fields.Char(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )
    pos_detailed_document_type_id = fields.Many2one(
        related="pos_config_id.detailed_document_type_id",
        store=True,
        readonly=False,
    )
    pos_detailed_document_type = fields.Char(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )
    pos_iface_fiscal_via_proxy = fields.Boolean(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )
    pos_sat_environment = fields.Selection(
        related="pos_config_id.sat_environment",
        store=True,
        readonly=False,
    )
    pos_cnpj_homologation = fields.Char(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )
    pos_ie_homologation = fields.Char(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )
    pos_cnpj_software_house = fields.Char(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )
    pos_sat_path = fields.Char(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )
    pos_cashier_number = fields.Integer(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )
    pos_activation_code = fields.Char(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )
    pos_signature_sat = fields.Char(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )
    pos_printer = fields.Selection(
        related="pos_config_id.printer",
        store=True,
        readonly=False,
    )
    pos_fiscal_printer_type = fields.Selection(
        related="pos_config_id.fiscal_printer_type",
        store=True,
        readonly=False,
    )
    pos_printer_params = fields.Char(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )
    pos_session_sat = fields.Integer(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )
    pos_ask_identity = fields.Boolean(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )
    pos_additional_data = fields.Text(
        compute="_compute_module_l10n_br_pos",
        store=True,
        readonly=False,
    )

    @api.depends("pos_config_id")
    def _compute_module_l10n_br_pos(self):
        for res_config in self:
            res_config.update(
                {
                    "pos_anonymous_simplified_limit": res_config.pos_config_id.anonymous_simplified_limit,
                    "pos_simplified_invoice_limit": res_config.pos_config_id.simplified_invoice_limit,
                    "pos_simplified_document_type": res_config.pos_config_id.simplified_document_type,
                    "pos_detailed_document_type": res_config.pos_config_id.detailed_document_type,
                    "pos_iface_fiscal_via_proxy": res_config.pos_config_id.iface_fiscal_via_proxy,
                    "pos_cnpj_homologation": res_config.pos_config_id.cnpj_homologation,
                    "pos_ie_homologation": res_config.pos_config_id.ie_homologation,
                    "pos_cnpj_software_house": res_config.pos_config_id.cnpj_software_house,
                    "pos_sat_path": res_config.pos_config_id.sat_path,
                    "pos_cashier_number": res_config.pos_config_id.cashier_number,
                    "pos_activation_code": res_config.pos_config_id.activation_code,
                    "pos_signature_sat": res_config.pos_config_id.signature_sat,
                    "pos_printer_params": res_config.pos_config_id.printer_params,
                    "pos_session_sat": res_config.pos_config_id.session_sat,
                    "pos_ask_identity": res_config.pos_config_id.ask_identity,
                    "pos_additional_data": res_config.pos_config_id.additional_data,
                }
            )
