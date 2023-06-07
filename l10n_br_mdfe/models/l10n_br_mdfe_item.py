# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

from ..constants.mdfe import (FISCAL_MODEL, FISCAL_MODEL_NFE, SITUATION_NFE,
                              SITUATION_NFE_AUTORIZADA)


class L10nBrMdfeItem(models.Model):

    _name = 'l10n_br.mdfe.item'
    _description = 'Documento MDF-E Carga Item'
    # _rec_name = 'document_key',

    @api.depends('document_key')
    def _compute_datas(self):
        for record in self:
            if record.document_key:
                record.document_model = record.document_key[20:22]
                record.document_serie = record.document_key[23:25]
                record.document_number = record.document_key[26:35]

    def _compute_document_information(self):
        for record in self:
            if record.document_id:
                volume_ids = record.document_id.volume_ids
                quantity = sum(line.quantity for line in volume_ids)
                net_weight = sum(line.net_weight for line in volume_ids)
                gross_weight = sum(line.gross_weight for line in volume_ids)
                # volume_liquido = sum(record.document_id.volume_ids.volume)
                # TODO: Taxa a ser configurada nas configuracões do módulo
                # taxa = 0.1
                # volume = volume_liquido * (1 + taxa)
                record.update({
                    'quantity': quantity,
                    'net_weight': net_weight,
                    'gross_weight': gross_weight,
                    # 'volume_liquido': volume_liquido,
                })

    mdfe_id = fields.Many2one(
        comodel_name='l10n_br_fiscal.document',
    )
    sender_id = fields.Many2one(
        comodel_name='res.partner',
        string='Remetente',
    )
    sender_city_id = fields.Many2one(
        comodel_name='res.city',
        string='Cidade remetente',
    )
    receiver_id = fields.Many2one(
        comodel_name='res.partner',
        string='Destinatario',
    )
    receiver_city_id = fields.Many2one(
        comodel_name='res.city',
        string='Cidade destinatário',
    )
    request_datetime = fields.Datetime(
        string='Solicitação',
        default=lambda self: fields.Datetime.now(),
        readonly=True,
    )
    loading_datetime = fields.Datetime()
    expedition_datetime = fields.Datetime()
    delivery_datetime = fields.Datetime()
    notes = fields.Text()

    document_id = fields.Many2one(
        comodel_name='l10n_br_fiscal.document',
        domain=[('document_type', '=', [FISCAL_MODEL_NFE]), ('document_number', '!=', 0),
                ('cfop_id.code', 'not in', ['5922', '6922']),
                ('situation_mdfe', '=', SITUATION_NFE_AUTORIZADA),
                '|', ('referenced_item_ids', '=', False),
                ('referenced_item_ids.mdfe_id.situation_mdfe', '!=', 'autorizada')],
        string='NF-E/CT-E',
    )
    document_key = fields.Char(
        string='Key',
        copy=False,

    )
    document_model = fields.Selection(
        selection=FISCAL_MODEL,
        string='Fiscal Model',
        index=True,
        compute=_compute_datas,
    )
    document_serie = fields.Char(
        string='Serie',
        index=True,
        compute=_compute_datas,
    )
    document_number = fields.Float(
        string='Number',
        index=True,
        readonly=True,
        digits=(18, 0),
        compute=_compute_datas,
    )
    document_status = fields.Selection(
        related='document_id.situation_mdfe',
        selection=SITUATION_NFE,
        string='Status',
        readonly=True,
    )

    net_weight = fields.Float(
        compute='_compute_document_information',
        store=True,
    )
    gross_weight = fields.Float(
        compute='_compute_document_information',
        store=True,
    )
    quantity = fields.Float(
        compute='_compute_document_information',
        store=True,
    )
    net_volume = fields.Float(
        compute='_compute_document_information',
        store=True,
    )
    gross_volume = fields.Float(
        compute='_compute_document_information',
        store=True,
    )

    @api.onchange('document_key')
    def _onchange_key(self):
        if self.document_key:
            self.document_id = self.document_id.search(
                [('document_key', '=', self.document_key)]
            )

    @api.onchange('document_id')
    def _onchange_document(self):

        if self.document_id:
            self.document_key = self.document_id.key
            self.receiver_city_id = self.document_id.participante_municipio_id
            self.receiver_id = self.document_id.participante_id

            self.sender_city_id = self.document_id.company_id.municipio_id.id
            self.sender_id = self.document_id.company_id.participante_id.id
