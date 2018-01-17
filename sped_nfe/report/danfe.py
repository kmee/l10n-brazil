from __future__ import with_statement
from odoo.report.interface import report_int
from odoo import api
from openerp import pooler

from odoo.addons.sped_nfe.models.inherited_sped_documento.py import gera_pdf


class report_custom(report_int):
    '''
        Custom report for return danfe
    '''

    @api.multi
    def create(self, cr, uid, ids, datas, context=None):
        context = context or {}
        active_ids = context.get('active_ids')
        pool = pooler.get_pool(cr.dbname)

        ai_obj = pool.get('sped.documento')
        sped_documento = ai_obj.browse(cr, uid, active_ids)

        gera_pdf(sped_documento)

report_custom('report.danfe_sped_documento')
