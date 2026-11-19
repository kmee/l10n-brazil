# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.osv import expression

SEARCH_CONTEXT_KEY = "dfe_import_uom_search"


class Uom(models.Model):
    _inherit = "uom.uom"

    @api.model
    def _name_search(
        self, name="", args=None, operator="ilike", limit=100, name_get_uid=None
    ):
        if not (self.env.context.get(SEARCH_CONTEXT_KEY) and name):
            return super()._name_search(name, args, operator, limit, name_get_uid)
        # the way the user thinks of a unit: by its fiscal code or its alias
        domain = [
            "|",
            "|",
            ("code", operator, name),
            ("alias_ids.code", operator, name),
            ("name", operator, name),
        ]
        return self._search(
            expression.AND([domain, args or []]),
            limit=limit,
            access_rights_uid=name_get_uid,
        )
