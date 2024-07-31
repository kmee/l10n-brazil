# Copyright (C) 2009 - TODAY Renato Lima - Akretion
# Copyright (C) 2019 - TODAY Raphaël Valyi - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
# pylint: disable=api-one-deprecated

from contextlib import contextmanager

from odoo import _, api, fields, models
from odoo.tools import frozendict

from .account_move import InheritsCheckMuteLogger

# These fields have the same name in account.move.line
# and l10n_br_fiscal.document.line. So they wouldn't get updated
# by the _inherits system. An alternative would be changing their name
# in l10n_br_fiscal but that would make the code unreadable and fiscal mixin
# methods would fail to do what we expect from them in the Odoo objects
# where they are injected.
# Fields that are related in l10n_br_fiscal.document.line like partner_id or company_id
# don't need to be written through the account.move.line write.
SHADOWED_FIELDS = [
    "product_id",
    "name",
    "quantity",
    "price_unit",
]

ACCOUNTING_FIELDS = ("debit", "credit", "amount_currency")
BUSINESS_FIELDS = ("price_unit", "quantity", "discount", "tax_ids")


class AccountMoveLine(models.Model):
    _name = "account.move.line"
    _inherit = [_name, "l10n_br_fiscal.document.line.mixin.methods"]
    _inherits = {"l10n_br_fiscal.document.line": "fiscal_document_line_id"}

    fiscal_document_line_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document.line",
        string="Fiscal Document Line",
        copy=False,
        ondelete="cascade",
    )

    document_type_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document.type",
        related="move_id.document_type_id",
    )

    tax_framework = fields.Selection(
        related="move_id.company_id.tax_framework",
        string="Tax Framework",
    )

    cfop_destination = fields.Selection(
        related="cfop_id.destination", string="CFOP Destination"
    )

    partner_company_type = fields.Selection(related="partner_id.company_type")

    ind_final = fields.Selection(related="move_id.ind_final")

    fiscal_genre_code = fields.Char(
        related="fiscal_genre_id.code",
        string="Fiscal Product Genre Code",
    )

    # The following fields belong to the fiscal document line mixin
    # but they are redefined here to ensure they are recomputed in the
    # account.move.line views.
    icms_cst_code = fields.Char(
        related="icms_cst_id.code",
        string="ICMS CST Code",
    )

    ipi_cst_code = fields.Char(
        related="ipi_cst_id.code",
        string="IPI CST Code",
    )

    cofins_cst_code = fields.Char(
        related="cofins_cst_id.code",
        string="COFINS CST Code",
    )

    cofinsst_cst_code = fields.Char(
        related="cofinsst_cst_id.code",
        string="COFINS ST CST Code",
    )

    pis_cst_code = fields.Char(
        related="pis_cst_id.code",
        string="PIS CST Code",
    )

    pisst_cst_code = fields.Char(
        related="pisst_cst_id.code",
        string="PIS ST CST Code",
    )

    partner_is_public_entity = fields.Boolean(related="partner_id.is_public_entity")

    allow_csll_irpj = fields.Boolean(
        compute="_compute_allow_csll_irpj",
    )

    discount = fields.Float(
        compute="_compute_discounts",
        store=True,
    )

    payment_term_number = fields.Char(
        help="Stores the installment number in the format 'current-total'. For example, "
        "'1-3' for the first of three installments, '2-3' for the second, and '3-3'"
        " for the last installment.",
    )

    @api.depends(
        "quantity",
        "price_unit",
        "discount_value",
    )
    def _compute_discounts(self):
        for line in self:
            line.discount = (line.discount_value * 100) / (
                line.quantity * line.price_unit or 1
            )

    @api.depends("product_id", "payment_term_number")
    def _compute_name(self):
        """
        Override to set 'name' with 'document_number/payment_term_number' for
        payment term lines. For other lines, it calls the superclass method.
        """
        payment_term_lines = self.filtered(
            lambda line: line.display_type == "payment_term"
            and line.document_type_id
            and line.move_id.document_number
            and line.payment_term_number
        )
        for line in payment_term_lines:
            # set label for payment term lines. Ex: '0001/1-3'
            line.name = f"{line.move_id.document_number}/{line.payment_term_number}"

        other_lines = self - payment_term_lines
        if other_lines:
            return super()._compute_name()
        return True

    @api.model
    def _inherits_check(self):
        """
        Overriden to avoid the super method to set the fiscal_document_line_id
        field as required.
        """
        with InheritsCheckMuteLogger("odoo.models"):  # mute spurious warnings
            res = super()._inherits_check()
        field = self._fields.get("fiscal_document_line_id")
        field.required = False  # unset the required = True assignement
        return res

    @api.model
    def _shadowed_fields(self):
        """Return the list of shadowed fields that are synchronized
        from account.move.line."""
        return SHADOWED_FIELDS

    @api.model
    def _inject_shadowed_fields(self, vals_list):
        for vals in vals_list:
            for field in self._shadowed_fields():
                if field in vals:
                    vals["fiscal_%s" % (field,)] = vals[field]

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("fiscal_document_line_id"):
                fiscal_line_data = (
                    self.env["l10n_br_fiscal.document.line"]
                    .browse(values["fiscal_document_line_id"])
                    .read(self._shadowed_fields())[0]
                )
                for k, v in fiscal_line_data.items():
                    if isinstance(v, tuple):  # m2o
                        values[k] = v[0]
                    else:
                        values[k] = v
                continue

            if values.get("exclude_from_invoice_tab"):
                continue

            move_id = self.env["account.move"].browse(values["move_id"])
            fiscal_doc_id = move_id.fiscal_document_id.id

            if not fiscal_doc_id:
                continue

            values.update(
                self._update_fiscal_quantity(
                    values.get("product_id"),
                    values.get("price_unit"),
                    values.get("quantity"),
                    values.get("product_uom_id"),
                    values.get("uot_id"),
                )
            )
            values["uom_id"] = values.get("product_uom_id")
            values["document_id"] = fiscal_doc_id  # pass through the _inherits system

            if False and (  # FIXME migrate
                move_id.is_invoice(include_receipts=True)
                and move_id.company_id.country_id.code == "BR"
                and any(
                    values.get(field)
                    for field in [*ACCOUNTING_FIELDS, *BUSINESS_FIELDS]
                )
            ):
                # TODO migrate!
                fisc_values = {
                    key: values[key]
                    for key in self.env["l10n_br_fiscal.document.line"]._fields.keys()
                    if values.get(key)
                }
                fiscal_line = self.env["l10n_br_fiscal.document.line"].new(fisc_values)
                fiscal_line._compute_amounts()
                cfop = values.get("cfop_id")
                cfop_id = (
                    self.env["l10n_br_fiscal.cfop"].browse(cfop) if cfop else False
                )
                values.update(
                    self._get_amount_credit_debit_model(  # TODO migrate!
                        move_id,
                        exclude_from_invoice_tab=values.get(
                            "exclude_from_invoice_tab", False
                        ),
                        amount_tax_included=values.get("amount_tax_included", 0),
                        amount_tax_not_included=values.get(
                            "amount_tax_not_included", 0
                        ),
                        amount_total=fiscal_line.amount_total,
                        currency_id=move_id.currency_id,
                        company_id=move_id.company_id,
                        date=move_id.date,
                        cfop_id=cfop_id,
                    )
                )
        self._inject_shadowed_fields(vals_list)

        # This reordering bellow is crucial to ensure accurate linkage between
        # account.move.line (aml) and the fiscal document line. In the fiscal create a
        # fiscal document line, leaving only those that should be created. Proper
        # ordering is essential as mismatches between the order of amls and the
        # manipulated vals_list of fiscal documents can lead to incorrect linkages.
        # For example, if vals_list[0] in amls does not match vals_list[0] in the
        # fiscal document (which is a manipulated vals_list), it results in erroneous
        # associations.

        # Add index to each dictionary in vals_list
        indexed_vals_list = [(idx, val) for idx, val in enumerate(vals_list)]

        # Reorder vals_list so lines with fiscal_operation_line_id will
        # be created first
        sorted_indexed_vals_list = sorted(
            indexed_vals_list,
            key=lambda x: not x[1].get("fiscal_operation_line_id"),
        )
        original_indexes = [idx for idx, _ in sorted_indexed_vals_list]
        vals_list = [val for _, val in sorted_indexed_vals_list]

        # Create the records
        result = super(
            AccountMoveLine, self.with_context(create_from_move_line=True)
        ).create(vals_list)

        # Initialize the inverted index list with the same length as the original list
        inverted_index = [0] * len(original_indexes)

        # Iterate over the original_indexes list and fill the inverted_index list accordingly
        for i, val in enumerate(original_indexes):
            inverted_index[val] = i

        # Re-order the result according to the initial vals_list order
        sorted_result = self.env["account.move.line"]
        for idx in inverted_index:
            sorted_result |= result[idx]

        # TODO MIGRATE, see https://github.com/OCA/l10n-brazil/pull/3037
        # for line in sorted_result:
        # Forces the recalculation of price_total and price_subtotal fields which are
        # recalculated by super
        # if line.move_id.company_id.country_id.code == "BR":
        #    line.update(line._get_price_total_and_subtotal())

        return sorted_result

    def TODO_write(self, values):  # KO FIXME !!!
        values["uom_id"] = values.get("product_uom_id")
        non_dummy = self.filtered(lambda line: line.fiscal_document_line_id)
        self._inject_shadowed_fields([values])
        if values.get("move_id") and len(non_dummy) == len(self):
            # we can write the document_id in all lines
            values["document_id"] = (
                self.env["account.move"].browse(values["move_id"]).fiscal_document_id.id
            )
            result = super().write(values)
        elif values.get("move_id"):
            # we will only define document_id for non dummy lines
            result = super().write(values)
            doc_id = (
                self.env["account.move"].browse(values["move_id"]).fiscal_document_id.id
            )
            super(AccountMoveLine, non_dummy).write({"document_id": doc_id})
        else:
            result = super().write(values)

        for line in self:
            cleaned_vals = line.move_id._cleanup_write_orm_values(line, values)
            if not cleaned_vals:
                continue

            if not line.move_id.is_invoice(include_receipts=True):
                continue

            if any(
                field in cleaned_vals
                for field in [*ACCOUNTING_FIELDS, *BUSINESS_FIELDS]
            ):
                to_write = line._get_amount_credit_debit_model(
                    line.move_id,
                    exclude_from_invoice_tab=line.exclude_from_invoice_tab,
                    amount_tax_included=line.amount_tax_included,
                    amount_tax_not_included=line.amount_tax_not_included,
                    amount_total=line.amount_total,
                    currency_id=line.currency_id,
                    company_id=line.company_id,
                    date=line.date,
                    cfop_id=line.cfop_id,
                )
                result |= super(AccountMoveLine, line).write(to_write)

        return result

    def unlink(self):
        unlink_fiscal_lines = self.env["l10n_br_fiscal.document.line"]
        for inv_line in self:
            if not inv_line.exists():
                continue
            if inv_line.fiscal_document_line_id:
                unlink_fiscal_lines |= inv_line.fiscal_document_line_id
        result = super().unlink()
        unlink_fiscal_lines.unlink()
        self.clear_caches()
        return result

    @contextmanager
    def _sync_invoice(self, container):
        """
        Almost the same as the super method from the account module.
        Overriden only to change one line where country_id.code is compared with "BR"
        """
        if container["records"].env.context.get("skip_invoice_line_sync"):
            yield
            return  # avoid infinite recursion

        def existing():
            return {
                line: {
                    "amount_currency": line.currency_id.round(line.amount_currency),
                    "balance": line.company_id.currency_id.round(line.balance),
                    "currency_rate": line.currency_rate,
                    "price_subtotal": line.currency_id.round(line.price_subtotal),
                    "move_type": line.move_id.move_type,
                }
                for line in container["records"]
                .with_context(
                    skip_invoice_line_sync=True,
                )
                .filtered(lambda l: l.move_id.is_invoice(True))
            }

        def changed(fname):
            return line not in before or before[line][fname] != after[line][fname]

        before = existing()
        yield
        after = existing()
        for line in after:
            if (
                line.move_id.company_id.country_id.code != "BR"  # LINE ADDED!
                and line.display_type == "product"
                and (not changed("amount_currency") or line not in before)
            ):
                amount_currency = line.move_id.direction_sign * line.currency_id.round(
                    line.price_subtotal
                )
                if line.amount_currency != amount_currency or line not in before:
                    line.amount_currency = amount_currency
                if line.currency_id == line.company_id.currency_id:
                    line.balance = amount_currency

        after = existing()
        for line in after:
            if (
                changed("amount_currency")
                or changed("currency_rate")
                or changed("move_type")
            ) and (not changed("balance") or (line not in before and not line.balance)):
                balance = line.company_id.currency_id.round(
                    line.amount_currency / line.currency_rate
                )
                line.balance = balance
        # Since this method is called during the sync, inside of `create`/`write`,
        # these fields
        # already have been computed and marked as so. But this method should
        # re-trigger it since
        # it changes the dependencies.
        self.env.add_to_compute(self._fields["debit"], container["records"])
        self.env.add_to_compute(self._fields["credit"], container["records"])

    # TODO As the accounting behavior of taxes in Brazil is completely different,
    # for now the method for companies in Brazil brings an empty result.
    # You can correctly map this behavior later.
    # TODO MIGRATE, no such method in v16, see https://github.com/OCA/l10n-brazil/pull/3037
    @api.model
    def _get_fields_onchange_balance_model(
        self,
        quantity,
        discount,
        amount_currency,
        move_type,
        currency,
        taxes,
        price_subtotal,
        force_computation=False,
    ):
        res = super()._get_fields_onchange_balance_model(
            quantity=quantity,
            discount=discount,
            amount_currency=amount_currency,
            move_type=move_type,
            currency=currency,
            taxes=taxes,
            price_subtotal=price_subtotal,
            force_computation=force_computation,
        )
        if (self.env.company.country_id.code == "BR") and (
            not self.exclude_from_invoice_tab and "price_unit" in res
        ):
            res = {}

        return res

    @api.depends(
        "quantity", "discount", "price_unit", "tax_ids", "currency_id", "discount"
    )  # TODO complete!
    def _compute_totals(self):
        """
        Overriden to pass all the Brazilian parameters we need
        to the account.tax#compute_all method.
        """
        result = super()._compute_totals()
        if not self.move_id.fiscal_operation_id:
            return result

        for line in self:
            if line.display_type != "product":
                continue  # handled in super method

            line_discount_price_unit = line.price_unit * (1 - (line.discount / 100.0))

            # Compute 'price_total'.
            if line.tax_ids:
                # force_sign = (
                #     -1
                #     if line.move_type in ("out_invoice", "in_refund", "out_receipt")
                #     else 1
                # )
                taxes_res = line.tax_ids._origin.with_context(
                    #                    force_sign=force_sign
                ).compute_all(
                    line_discount_price_unit,
                    currency=line.currency_id,
                    quantity=line.quantity,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.move_type in ("out_refund", "in_refund"),
                    handle_price_include=True,  # FIXME
                    fiscal_taxes=line.fiscal_tax_ids,
                    operation_line=line.fiscal_operation_line_id,
                    cfop=line.cfop_id or None,
                    ncm=line.ncm_id,
                    nbs=line.nbs_id,
                    nbm=line.nbm_id,
                    cest=line.cest_id,
                    discount_value=line.discount_value,
                    insurance_value=line.insurance_value,
                    other_value=line.other_value,
                    ii_customhouse_charges=line.ii_customhouse_charges,
                    freight_value=line.freight_value,
                    fiscal_price=line.fiscal_price,
                    fiscal_quantity=line.fiscal_quantity,
                    uot_id=line.uot_id,
                    icmssn_range=line.icmssn_range_id,
                    icms_origin=line.icms_origin,
                    ind_final=line.ind_final,
                )

                line.price_subtotal = taxes_res["total_excluded"]
                line.price_total = taxes_res["total_included"]
                line._compute_balance()

            line.price_total += (
                line.insurance_value + line.other_value + line.freight_value
            )
            # - icms_relief_value ?  TODO MIGRATE
            # (see https://github.com/OCA/l10n-brazil/pull/3037 )
        return result

    @api.depends(
        "tax_ids",
        "currency_id",
        "partner_id",
        "analytic_distribution",
        "balance",
        "partner_id",
        "move_id.partner_id",
        "price_unit",
    )
    def _compute_all_tax(self):
        """
        Overriden to pass all the extra Brazilian parameters we need
        to the account.tax#compute_all method.
        """
        # TODO seems we should use sign in account_tax#compute_all
        # so base and amount are negative if move is in.
        if not self.move_id.fiscal_operation_id:
            return super()._compute_all_tax()

        for line in self:
            sign = line.move_id.direction_sign
            if line.display_type == "tax":
                line.compute_all_tax = {}
                line.compute_all_tax_dirty = False
                continue
            if line.display_type == "product" and line.move_id.is_invoice(True):
                amount_currency = sign * line.price_unit * (1 - line.discount / 100)
                handle_price_include = True
                quantity = line.quantity
            else:
                amount_currency = line.amount_currency
                handle_price_include = False
                quantity = 1
            compute_all_currency = line.tax_ids.compute_all(
                amount_currency,
                currency=line.currency_id,
                quantity=quantity,
                product=line.product_id,
                partner=line.move_id.partner_id or line.partner_id,
                is_refund=line.is_refund,
                handle_price_include=handle_price_include,
                include_caba_tags=line.move_id.always_tax_exigible,
                fixed_multiplicator=sign,
                fiscal_taxes=line.fiscal_tax_ids,
                operation_line=line.fiscal_operation_line_id,
                cfop=line.cfop_id or None,
                ncm=line.ncm_id,
                nbs=line.nbs_id,
                nbm=line.nbm_id,
                cest=line.cest_id,
                discount_value=line.discount_value,
                insurance_value=line.insurance_value,
                other_value=line.other_value,
                ii_customhouse_charges=line.ii_customhouse_charges,
                freight_value=line.freight_value,
                fiscal_price=line.fiscal_price,
                fiscal_quantity=line.fiscal_quantity,
                uot_id=line.uot_id,
                icmssn_range=line.icmssn_range_id,
                icms_origin=line.icms_origin,
                ind_final=line.ind_final,
            )
            rate = (
                line.amount_currency / line.balance
                if (line.balance and line.amount_currency)
                else 1
            )
            line.compute_all_tax_dirty = True
            line.compute_all_tax = {
                frozendict(
                    {
                        "tax_repartition_line_id": tax["tax_repartition_line_id"],
                        "group_tax_id": tax["group"] and tax["group"].id or False,
                        "account_id": tax["account_id"] or line.account_id.id,
                        "currency_id": line.currency_id.id,
                        "analytic_distribution": (
                            tax["analytic"] or not tax["use_in_tax_closing"]
                        )
                        and line.analytic_distribution,
                        "tax_ids": [(6, 0, tax["tax_ids"])],
                        "tax_tag_ids": [(6, 0, tax["tag_ids"])],
                        "partner_id": line.move_id.partner_id.id or line.partner_id.id,
                        "move_id": line.move_id.id,
                        "display_type": line.display_type,
                    }
                ): {
                    "name": tax["name"]
                    + (" " + _("(Discount)") if line.display_type == "epd" else ""),
                    "balance": tax["amount"] / rate,
                    "amount_currency": tax["amount"],
                    "tax_base_amount": tax["base"]
                    / rate
                    * (-1 if line.tax_tag_invert else 1),
                }
                for tax in compute_all_currency["taxes"]
                if tax["amount"]
            }
            if not line.tax_repartition_line_id:
                line.compute_all_tax[frozendict({"id": line.id})] = {
                    "tax_tag_ids": [(6, 0, compute_all_currency["base_tags"])],
                }

    @api.onchange("fiscal_document_line_id")
    def _onchange_fiscal_document_line_id(self):
        if self.fiscal_document_line_id:
            for field in self._shadowed_fields():
                value = getattr(self.fiscal_document_line_id, field)
                if isinstance(value, tuple):  # m2o
                    setattr(self, field, value[0])
                else:
                    setattr(self, field, value)
            # override the default product uom (set by the onchange):
            self.product_uom_id = self.fiscal_document_line_id.uom_id.id

    @api.onchange("fiscal_tax_ids")
    def _onchange_fiscal_tax_ids(self):
        """Ao alterar o campo fiscal_tax_ids que contém os impostos fiscais,
        são atualizados os impostos contábeis relacionados"""
        result = super()._onchange_fiscal_tax_ids()

        # Atualiza os impostos contábeis relacionados aos impostos fiscais
        user_type = "sale"
        if self.move_id.move_type in ("in_invoice", "in_refund"):
            user_type = "purchase"

        self.tax_ids = self.fiscal_tax_ids.account_taxes(
            user_type=user_type, fiscal_operation=self.fiscal_operation_id
        )

        return result

    # @api.onchange(
    #     "amount_currency",
    #     "currency_id",
    #     "debit",
    #     "credit",
    #     "tax_ids",
    #     "fiscal_tax_ids",
    #     "account_id",
    #     "price_unit",
    #     "quantity",
    #     "fiscal_quantity",
    #     "fiscal_price",
    # )
    # def _onchange_mark_recompute_taxes(self):  FIXME no such meth in v16
    #     """Recompute the dynamic onchange based on taxes.
    #     If the edited line is a tax line, don't recompute anything as the
    #     user must be able to set a custom value.
    #     """
    #     return super()._onchange_mark_recompute_taxes()

    # @api.model
    # def TODO_get_fields_onchange_subtotal_model(  # no such meth in v16
    #     self, price_subtotal, move_type, currency, company, date
    # ):
    #     if company.country_id.code != "BR":
    #         return super()._get_fields_onchange_subtotal_model(
    #             price_subtotal=price_subtotal,
    #             move_type=move_type,
    #             currency=currency,
    #             company=company,
    #             date=date,
    #         )
    # In l10n_br, the calc of these fields is done in the
    # _get_amount_credit_debit method, as the calculation method
    # is completely different.
    # return {}

    # These fields are already inherited by _inherits, but there is some limitation of
    # the ORM that the values of these fields are zeroed when called by onchange. This
    # limitation directly affects the _get_amount_credit_debit method.
    amount_untaxed = fields.Monetary(compute="_compute_amounts")
    amount_total = fields.Monetary(compute="_compute_amounts")

    # def _onchange_price_subtotal(self):  # TODO no such meth in v16
    # TODO remove: replaced by _compute_totals and _compute_debit_credit (TODO)
    #   [...]
    #         line.update(line._get_price_total_and_subtotal())
    #         line.update(line._get_amount_credit_debit())

    # TODO replace by def _compute_debit_credit !
    # def _get_amount_credit_debit(
    #     self,
    #     move_id=None,
    #     exclude_from_invoice_tab=None,
    #     amount_tax_included=None,
    #     amount_tax_not_included=None,
    #     amount_total=None,
    #     currency_id=None,
    #     company_id=None,
    #     date=None,
    #     cfop_id=None,
    # ):
    #     self.ensure_one()
    #     # The formatting was a little strange, but I tried to make it as close as
    #     # possible to the logic adopted by native Odoo.
    #     # Example: _get_fields_onchange_subtotal
    #     return self._get_amount_credit_debit_model(
    #         move_id=self.move_id if move_id is None else move_id,
    #         exclude_from_invoice_tab=self.exclude_from_invoice_tab
    #         if exclude_from_invoice_tab is None
    #         else exclude_from_invoice_tab,
    #         amount_tax_included=self.amount_tax_included
    #         if amount_tax_included is None
    #         else amount_tax_included,
    #         amount_tax_not_included=self.amount_tax_not_included
    #         if amount_tax_not_included is None
    #         else amount_tax_not_included,
    #         amount_total=self.amount_total if amount_total is None else amount_total,
    #         currency_id=self.currency_id if currency_id is None else currency_id,
    #         company_id=self.company_id if company_id is None else company_id,
    #         date=(self.date or fields.Date.context_today(self))
    #         if date is None
    #         else date,
    #         cfop_id=self.cfop_id if cfop_id is None else cfop_id,
    #     )

    # def _get_amount_credit_debit_model(
    #     self,
    #     move_id,
    #     exclude_from_invoice_tab,
    #     amount_tax_included,
    #     amount_tax_not_included,
    #     amount_total,
    #     currency_id,
    #     company_id,
    #     date,
    #     cfop_id,
    # ):

    @api.depends("move_id")
    def _compute_balance(self):
        res = super()._compute_balance()

        for line in self:
            if not line.move_id.is_invoice(
                include_receipts=True
            ) or line.display_type in ("line_section", "line_note"):
                continue  # handled in super method

            if line.move_id.move_type in line.move_id.get_outbound_types():
                sign = 1
            elif line.move_type in line.move_id.get_inbound_types():
                sign = -1
            else:
                sign = 1

            if line.cfop_id and not line.cfop_id.finance_move:
                line.balance = 0
            else:
                if line.move_id.fiscal_operation_id.deductible_taxes:
                    line.balance = sign * line.price_subtotal
                elif line.move_id.fiscal_operation_id:
                    line.balance = sign * (
                        line.price_subtotal - line.amount_tax_included
                    )
        return res
