# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models

# Who may see the secret part of an A1: the system administrators and the fiscal
# managers, the only groups that had access to the model before the bank
# connection administrators were allowed to choose a certificate.
CERTIFICATE_SECRET_GROUPS = "base.group_system,l10n_br_fiscal.group_manager"


class Certificate(models.Model):
    _inherit = "certificate.certificate"

    # The bank connection administrators read the certificates of their company
    # to pick one on a connection (access rule of the model, see
    # ir.model.access.csv). They never get the .pfx, its password or the private
    # key: those fields stay with the groups that managed the model so far.
    content = fields.Binary(groups=CERTIFICATE_SECRET_GROUPS)
    pkcs12_password = fields.Char(groups=CERTIFICATE_SECRET_GROUPS)
    private_key_id = fields.Many2one(groups=CERTIFICATE_SECRET_GROUPS)
    public_key_id = fields.Many2one(groups=CERTIFICATE_SECRET_GROUPS)
