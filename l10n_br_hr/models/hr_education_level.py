# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import models


class HrEducationLevel(models.Model):
    _name = "hr.education.level"
    _inherit = "l10n_br_hr.data.abstract"
    _description = "Education Levels (eSocial Table 01)"
