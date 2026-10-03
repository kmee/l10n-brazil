# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal.constants.fiscal import DOCUMENT_ISSUER_COMPANY
from odoo.addons.l10n_br_nfe.models.document import filter_processador_edoc_nfe

# leiauteNFe_v4.00.xsd: <rastro minOccurs="0" maxOccurs="500">
RASTRO_MAX_OCCURS = 500


class FiscalDocument(models.Model):
    _inherit = "l10n_br_fiscal.document"

    def _document_check(self):
        result = super()._document_check()
        for record in self.filtered(filter_processador_edoc_nfe):
            if record.issuer == DOCUMENT_ISSUER_COMPANY:
                record._check_nfe40_rastro()
        return result

    def _check_nfe40_rastro(self):
        """Refuse to issue an NF-e the SEFAZ would reject because of the
        traceability group: required fields, more than 500 lots, a
        manufacturing date after the issue date (rule I83-10, rejection
        877) or an expiration date before the manufacturing date (rule
        I84-10, rejection 870)."""
        self.ensure_one()
        issue_date = (
            fields.Datetime.context_timestamp(self, self.document_date).date()
            if self.document_date
            else fields.Date.context_today(self)
        )
        errors = []
        for line in self.fiscal_line_ids:
            item = line.product_id.display_name or line.name
            if line._nfe40_rastro_is_required() and not line.nfe40_rastro:
                errors.append(
                    _(
                        "%(item)s: the traceability group (lot number, quantity, "
                        "manufacturing and expiration dates) is required.",
                        item=item,
                    )
                )
            if len(line.nfe40_rastro) > RASTRO_MAX_OCCURS:
                errors.append(
                    _(
                        "%(item)s: the NF-e accepts at most %(max)s lots per item.",
                        item=item,
                        max=RASTRO_MAX_OCCURS,
                    )
                )
            for rastro in line.nfe40_rastro:
                lot = rastro.nfe40_nLote or "?"
                if not rastro.nfe40_nLote:
                    errors.append(_("%(item)s: lot number missing.", item=item))
                if not rastro.nfe40_dFab:
                    errors.append(
                        _(
                            "%(item)s, lot %(lot)s: manufacturing date missing.",
                            item=item,
                            lot=lot,
                        )
                    )
                elif rastro.nfe40_dFab > issue_date:
                    errors.append(
                        _(
                            "%(item)s, lot %(lot)s: the manufacturing date is "
                            "after the issue date.",
                            item=item,
                            lot=lot,
                        )
                    )
                if not rastro.nfe40_dVal:
                    errors.append(
                        _(
                            "%(item)s, lot %(lot)s: expiration date missing.",
                            item=item,
                            lot=lot,
                        )
                    )
                elif rastro.nfe40_dFab and rastro.nfe40_dVal < rastro.nfe40_dFab:
                    errors.append(
                        _(
                            "%(item)s, lot %(lot)s: the expiration date is before "
                            "the manufacturing date.",
                            item=item,
                            lot=lot,
                        )
                    )
        if errors:
            raise UserError(
                _(
                    "The NF-e traceability data (rastro) is incomplete or "
                    "inconsistent:\n%(errors)s",
                    errors="\n".join(errors),
                )
            )
