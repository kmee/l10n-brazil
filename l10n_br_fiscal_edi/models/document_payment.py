# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

# pylint: disable=consider-merging-classes-inherited

from dataclasses import replace

from odoo import _, api, fields, models

# The withholdings of the total of a document, which the document keeps apart from
# the lines when the file declares them only in the total (NF-e ``retTrib``).
DECLARED_WITHHOLDING_FIELDS = (
    "amount_pis_wh_base",
    "amount_pis_wh_value",
    "amount_cofins_wh_base",
    "amount_cofins_wh_value",
    "amount_csll_wh_base",
    "amount_csll_wh_value",
    "amount_irpj_wh_base",
    "amount_irpj_wh_value",
    "amount_inss_wh_base",
    "amount_inss_wh_value",
    "amount_issqn_wh_base",
    "amount_issqn_wh_value",
)
DECLARED_WITHHOLDING_VALUES = (
    "amount_pis_wh_value",
    "amount_cofins_wh_value",
    "amount_csll_wh_value",
    "amount_irpj_wh_value",
    "amount_inss_wh_value",
    "amount_issqn_wh_value",
)


class Document(models.Model):
    """What a fiscal document declares to be paid, and the page that shows it.

    The installments and the payments are read from the document by the module of
    its type (NF-e ``dup`` and ``detPag``, CT-e ``cobr``). Nothing here creates a
    payable: the titles are born when the invoice is generated.
    """

    _inherit = "l10n_br_fiscal.document"

    edi_payment_summary = fields.Html(
        compute="_compute_edi_payment_summary",
        sanitize=False,
        help="Installments and payments declared by the document and the totals "
        "that go with them. It is not stored.",
    )

    import_withholding_declared = fields.Boolean(
        copy=False,
        help="The file declared its withholdings only in the total, with no tax "
        "on the lines. The document then keeps the declared amounts (they are not "
        "the sum of the lines) and the net amount payable discounts them.",
    )

    def _edi_withholding_declared(self):
        """True when the withholdings of the document are the ones the file declared
        in its total: the lines carry none, so nothing is shared among them."""
        self.ensure_one()
        return bool(
            self.imported_document
            and self.import_withholding_declared
            and not sum(self.fiscal_line_ids.mapped("amount_tax_withholding"))
        )

    @api.depends(lambda self: self._get_fiscal_amount_field_dependencies())
    def _compute_fiscal_amount(self):
        """The sum of the lines would erase the withholdings that the file declared
        in its total: keep them."""
        kept = {
            document: {field: document[field] for field in DECLARED_WITHHOLDING_FIELDS}
            for document in self.filtered("import_withholding_declared")
            if document._edi_withholding_declared()
        }
        result = super()._compute_fiscal_amount()
        for document, values in kept.items():
            # The total is rebuilt from the declared amounts, never read back: it is
            # the field being computed and may answer zero while it is.
            values["amount_tax_withholding"] = sum(
                values[field] for field in DECLARED_WITHHOLDING_VALUES
            )
            document.update(values)
        return result

    def _edi_declared_withholding(self):
        """Sum of the withholdings that the file declared in its total."""
        self.ensure_one()
        return sum(self[field] for field in DECLARED_WITHHOLDING_VALUES)

    def _edi_get_installments(self):
        """Installments declared by the document, as a list of ``EdiInstallment``."""
        self.ensure_one()
        return []

    def _edi_get_payments(self):
        """Payments declared by the document, as a list of ``EdiPayment``."""
        self.ensure_one()
        return []

    def _edi_display_installments(self):
        """Installments the page shows. Who knows more than the declaration (the
        invoice that will issue the document) overrides it."""
        self.ensure_one()
        return self._edi_get_installments()

    def _edi_display_payments(self):
        """Payments the page shows."""
        self.ensure_one()
        return self._edi_get_payments()

    def _edi_payment_means_label(self, means):
        """Name of a means of payment (tPag), to show instead of its code. The module
        that knows the selection of the means answers; the base shows the code."""
        self.ensure_one()
        return means

    def _edi_payment_totals(self):
        """Gross total, withholdings and net amount payable, as ``(gross, withholding,
        net)``. The total of the document is already net of the withholdings and is
        the same for every type, but it is only computed when the document has a
        fiscal operation: a CT-e imported without one would show zero, so the lines,
        which carry the amounts declared in the file, answer instead."""
        self.ensure_one()
        if self._edi_withholding_declared():
            # the lines are gross: the withholdings of the total come off the amount
            # payable, and the installments of the file are not changed by them
            gross = (
                self.fiscal_amount_total
                if self.fiscal_operation_id
                else sum(self.fiscal_line_ids.mapped("fiscal_amount_total"))
            )
            withholding = self._edi_declared_withholding()
            return gross, withholding, gross - withholding
        if self.fiscal_operation_id:
            net, withholding = self.fiscal_amount_total, self.amount_tax_withholding
        else:
            lines = self.fiscal_line_ids
            net = sum(lines.mapped("fiscal_amount_total"))
            withholding = sum(lines.mapped("amount_tax_withholding"))
        return net + withholding, withholding, net

    def _edi_installment_difference(self):
        """Net amount payable minus the sum of the installments shown."""
        self.ensure_one()
        installments = self._edi_display_installments()
        if not installments:
            return 0.0
        declared = sum(installment.amount for installment in installments)
        return self.currency_id.round(self._edi_payment_totals()[2] - declared)

    def _edi_installment_warning(self):
        """What the page tells about the installments and the invoice that will be
        generated, or False when there is nothing to tell.

        The invoice takes its total from the lines and the withholdings of the
        lines, and spreads that total over the declared installments by their
        weight, so a difference between the two is shared among them. The
        withholdings that the file declared only in its total are not in the lines:
        the invoice does not discount them, the installments of the file stay as
        they are and the net amount payable is only informative."""
        self.ensure_one()
        gross, withholding, net = self._edi_payment_totals()
        declared_withholding = self._edi_withholding_declared()
        # what the invoice will total, and so what it spreads over the installments
        invoiced = gross if declared_withholding else net
        installments = self._edi_display_installments()
        declared = sum(installment.amount for installment in installments)
        messages = []
        if installments and self.currency_id.round(invoiced - declared):
            messages.append(
                _(
                    "The declared installments add up to %(declared)s; the net "
                    "amount payable is %(net)s. The invoice spreads the difference "
                    "by the weight of each installment."
                )
                % {"declared": f"{declared:.2f}", "net": f"{invoiced:.2f}"}
            )
        if declared_withholding and withholding:
            messages.append(
                _(
                    "The note declares withholdings of %(withholding)s in its "
                    "total. The invoice generated from it does not discount them: "
                    "its total and its installments stay as in the file, gross of "
                    "the withholdings, so the net amount payable of %(net)s is only "
                    "informative and the withholdings must be recorded in the "
                    "invoice."
                )
                % {"withholding": f"{withholding:.2f}", "net": f"{net:.2f}"}
            )
        return " ".join(messages) or False

    def _edi_payment_summary_values(self):
        """Values of the template ``document_payment_summary``, which the invoice
        reuses to show the same page. Empty when there is nothing to show."""
        self.ensure_one()
        installments = self._edi_display_installments()
        payments = self._edi_display_payments()
        gross, withholding, net = self._edi_payment_totals()
        if not (installments or payments or (self.imported_document and withholding)):
            return {}
        return {
            "currency": self.currency_id,
            "installments": installments,
            "payments": [
                replace(payment, label=self._edi_payment_means_label(payment.means))
                for payment in payments
            ],
            "totals": [
                (_("Document total"), gross),
                (_("Withholdings"), withholding),
                (_("Net amount payable"), net),
            ],
            "warning": self._edi_installment_warning(),
        }

    @api.depends(
        "imported_document",
        "state_edoc",
        "fiscal_operation_id",
        "fiscal_amount_total",
        "amount_tax_withholding",
        "import_withholding_declared",
        "fiscal_line_ids.fiscal_amount_total",
        "fiscal_line_ids.amount_tax_withholding",
    )
    def _compute_edi_payment_summary(self):
        for document in self:
            values = document._edi_payment_summary_values()
            document.edi_payment_summary = (
                self.env["ir.qweb"]._render(
                    "l10n_br_fiscal_edi.document_payment_summary", values
                )
                if values
                else False
            )

    def _edi_import_warnings(self):
        messages = super()._edi_import_warnings()
        warning = self._edi_installment_warning()
        if self.imported_document and warning:
            messages.append(warning)
        return messages

    def _edi_set_installments(self, installments):
        """Write the installments of an issued document in the tags of its type.

        :param installments: list of ``EdiInstallment``. The module of each
            document type overrides it; the base has nothing to write.
        """
        self.ensure_one()

    def _edi_set_payments(self, payments):
        """Write the payments of an issued document in the tags of its type.

        :param payments: list of ``EdiPayment``. The module of each document type
            overrides it; the base has nothing to write.
        """
        self.ensure_one()
