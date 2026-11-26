from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..models.nfe_md_event import JUSTIFICATION_MAX_SIZE, JUSTIFICATION_MIN_SIZE


class NfeRecipientManifestationEventWizard(models.TransientModel):
    _name = "nfe_recipient_manifestation_event.wizard"
    _description = "Wizard to manifest"

    access_key = fields.Char(size=44, required=True)

    event_type = fields.Selection(
        selection=[
            ("ciente", "Ciente da Operação"),
            ("confirmado", "Confirmada operação"),
            ("desconhecido", "Desconhecimento"),
            ("nao_realizado", "Não realizado"),
        ],
        default="ciente",
        required=True,
    )

    justification = fields.Text(
        help="Reason of the 'Operação não Realizada' event, sent to SEFAZ "
        "(15 to 255 characters).",
    )

    @api.constrains("event_type", "justification")
    def _check_justification(self):
        for record in self.filtered(lambda r: r.event_type == "nao_realizado"):
            size = len((record.justification or "").strip())
            if not JUSTIFICATION_MIN_SIZE <= size <= JUSTIFICATION_MAX_SIZE:
                raise ValidationError(
                    _(
                        "The justification must have between %(min)s and %(max)s"
                        " characters.",
                        min=JUSTIFICATION_MIN_SIZE,
                        max=JUSTIFICATION_MAX_SIZE,
                    )
                )

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        access_key = self.env.context.get("default_access_key")
        res.update({"access_key": access_key})
        return res

    def _get_justification(self):
        self.ensure_one()
        if self.event_type != "nao_realizado":
            return False
        return (self.justification or "").strip()

    def action_create_nfe_md_event(self):
        mde = self.env["l10n_br_nfe.md_event"].create(
            {
                "access_key": self.access_key,
                "event_type": self.event_type,
                "company_id": self.env.company.id,
                "document_type": "nfe",
                "state": "draft",
                "justification": self._get_justification(),
            }
        )

        mde.action_confirm()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("Recipient Manifestation created successfully"),
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
