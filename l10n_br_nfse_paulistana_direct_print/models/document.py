# Copyright (C) 2023 Antônio S. P. Neto <neto@engene.one> - Engenere LTDA (https://engenere.one).
# Copyright (C) 2023 Marcel Savegnago <marcel.savegnago@escodoo.com.br> - Escodoo (https://www.escodoo.com.br).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class Document(models.Model):

    _inherit = "l10n_br_fiscal.document"

    url_nfse_paulistana = fields.Char(
        string="URL of NFSe Paulistana",
        compute="_compute_url_nfse_paulistana",
        help="URL to access the Nota Fiscal de Serviços Eletrônicos (NFSe)"
        "from the São Paulo City (Paulistana).",
    )
    is_nfse_paulistana = fields.Boolean(
        string="Is NFSe Paulistana?",
        compute="_compute_is_nfse_paulistana",
        help="Technical field to identify if the document is a NFSe Paulistana.",
    )

    def _compute_url_nfse_paulistana(self):
        for doc in self:

            # requeried fields for the url
            nf = doc.document_number
            inscricao = doc.company_id.partner_id.l10n_br_im_code
            verificacao = doc.verify_code

            # skip if any of the required fields is empty
            if not all([nf, inscricao, verificacao]):
                doc.url_nfse_paulistana = ""
                continue

            nfse_print_url = (
                "https://nfe.prefeitura.sp.gov.br/contribuinte/notaprint.aspx?"
                f"nf={nf}&inscricao={inscricao}&verificacao={verificacao}"
            )
            doc.url_nfse_paulistana = nfse_print_url

    def action_open_nfse_paulistana(self):
        return {
            'type': 'ir.actions.act_url',
            'url': self.url_nfse_paulistana,
            'target': 'new',
        }

    def _compute_is_nfse_paulistana(self):
        for doc in self:
            is_nfse = doc.document_type == "SE"
            is_paulistana = doc.company_id.city_id == self.env.ref(
                "l10n_br_base.city_3550308"
            )

            if is_nfse and is_paulistana:
                doc.is_nfse_paulistana = True
            else:
                doc.is_nfse_paulistana = False
