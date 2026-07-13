# Copyright (C) 2009 - TODAY Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import Command, api, fields, models
from odoo.tools.misc import formatLang

from odoo.addons.l10n_br_fiscal.constants.fiscal import FINAL_CUSTOMER_NO


class AccountTax(models.Model):
    _inherit = "account.tax"

    fiscal_tax_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.tax",
        related="tax_group_id.fiscal_tax_group_id.tax_ids",
        string="Fiscal Taxes",
    )

    def compute_all(
        self,
        price_unit,
        currency=None,
        quantity=1.0,
        product=None,
        partner=None,
        is_refund=False,
        handle_price_include=True,
        include_caba_tags=False,
        fixed_multiplicator=1,
        fiscal_taxes=None,
        operation_line=False,
        ncm=None,
        nbs=None,
        nbm=None,
        cest=None,
        cfop=None,
        discount_value=None,
        insurance_value=None,
        other_value=None,
        ii_customhouse_charges=None,
        freight_value=None,
        fiscal_price=None,
        fiscal_quantity=None,
        uot_id=None,
        icmssn_range=None,
        icms_origin=None,
        ind_final=FINAL_CUSTOMER_NO,
        rounding_method=None,
    ):
        """Returns all information required to apply taxes
            (in self + their children in case of a tax goup).
            We consider the sequence of the parent for group of taxes.
                Eg. considering letters as taxes and alphabetic order
                as sequence :
                [G, B([A, D, F]), E, C] will be computed as [A, D, F, C, E, G]
        RETURN: {
            'total_excluded': 0.0,    # Total without taxes
            'total_included': 0.0,    # Total with taxes
            'taxes': [{               # One dict for each tax in self
                                      # and their children
                'id': int,
                'name': str,
                'amount': float,
                'sequence': int,
                'account_id': int,
                'refund_account_id': int,
                'analytic': boolean,
            }]
        }"""

        # fixed_multiplicator nao existe mais na assinatura do core (18.0) -
        # o slot posicional que ele ocupava agora e rounding_method; passar
        # fixed_multiplicator (int) ali corrompia o metodo de arredondamento
        # silenciosamente. is_refund (ja repassado acima) e o mecanismo atual
        # do core para o mesmo efeito de inverter sinal em devolucoes.
        taxes_results = super().compute_all(
            price_unit,
            currency,
            quantity,
            product,
            partner,
            is_refund,
            handle_price_include,
            include_caba_tags,
            rounding_method=rounding_method,
        )

        if not fiscal_taxes:
            fiscal_taxes = self.env["l10n_br_fiscal.tax"]

        product = product or self.env["product.product"]

        if len(self) == 0:
            company = self.env.company
            if self.env.context.get("default_company_id") or self.env.context.get(
                "allowed_company_ids"
            ):
                company = self.env["res.company"].browse(
                    self.env.context.get("default_company_id")
                    or self.env.context.get("allowed_company_ids")[0]
                )
        else:
            company = self[0].company_id

        fiscal_taxes_results = fiscal_taxes.compute_taxes(
            company=company,
            partner=partner,
            product=product,
            price_unit=price_unit,
            quantity=quantity,
            uom_id=product.uom_id,
            fiscal_price=fiscal_price or price_unit,
            fiscal_quantity=fiscal_quantity or quantity,
            uot_id=uot_id or product.uot_id,
            ncm=ncm or product.ncm_id,
            nbs=nbs or product.nbs_id,
            nbm=nbm or product.nbm_id,
            cest=cest or product.cest_id,
            cfop=cfop,
            discount_value=discount_value,
            insurance_value=insurance_value,
            other_value=other_value,
            ii_customhouse_charges=ii_customhouse_charges,
            freight_value=freight_value,
            operation_line=operation_line,
            icmssn_range=icmssn_range,
            icms_origin=icms_origin or product.icms_origin,
            ind_final=ind_final,
        )

        taxes_results["amount_tax_included"] = fiscal_taxes_results["amount_included"]
        taxes_results["amount_tax_not_included"] = fiscal_taxes_results[
            "amount_not_included"
        ]
        taxes_results["amount_tax_withholding"] = fiscal_taxes_results[
            "amount_withholding"
        ]
        taxes_results["amount_estimate_tax"] = fiscal_taxes_results["estimate_tax"]

        account_taxes_by_domain = {}

        sign = -1 if fixed_multiplicator < 0 else 1

        for tax in self:
            tax_domain = tax.tax_group_id.fiscal_tax_group_id.tax_domain
            account_taxes_by_domain.update({tax.id: tax_domain})

        for account_tax in taxes_results["taxes"]:
            tax = self.filtered(lambda t: t.id == account_tax.get("id"))  # noqa: B023
            fiscal_tax = fiscal_taxes_results["taxes"].get(
                account_taxes_by_domain.get(tax.id)
            )

            account_tax.update(
                {
                    "tax_group_id": tax.tax_group_id.id,
                    "deductible": tax.deductible,
                }
            )

            tax_repartition_lines = (
                is_refund
                and tax.refund_repartition_line_ids
                or tax.invoice_repartition_line_ids
            ).filtered(lambda x: x.repartition_type == "tax")

            sum_repartition_factor = sum(tax_repartition_lines.mapped("factor"))

            if fiscal_tax:
                if fiscal_tax.get("base") < 0:
                    sign = -1
                    fiscal_tax["base"] = -fiscal_tax.get("base")

                if not fiscal_tax.get("tax_include") and not tax.deductible:
                    taxes_results["total_included"] += fiscal_tax.get("tax_value")

                fiscal_group = tax.tax_group_id.fiscal_tax_group_id
                tax_amount = fiscal_tax.get("tax_value", 0.0) * sum_repartition_factor
                tax_base = fiscal_tax.get("base") * sum_repartition_factor
                if tax.deductible or fiscal_group.tax_withholding:
                    tax_amount = (
                        fiscal_tax.get("tax_value", 0.0) * sum_repartition_factor
                    )

                account_tax.update(
                    {
                        "id": account_tax.get("id"),
                        "name": fiscal_group.name,
                        "fiscal_name": fiscal_tax.get("name"),
                        "base": tax_base * sign,
                        "tax_include": fiscal_tax.get("tax_include"),
                        "amount": tax_amount * sign,
                        "fiscal_tax_id": fiscal_tax.get("fiscal_tax_id"),
                        "tax_withholding": fiscal_group.tax_withholding,
                    }
                )

        return taxes_results

    @api.model
    def _compute_taxes_for_single_line(
        self,
        base_line,
        handle_price_include=True,
        include_caba_tags=False,
        early_pay_discount_computation=None,
        early_pay_discount_percentage=None,
    ):
        """
        Similar to the _compute_taxes_for_single_line super method in the account module
        but overriden to pass extra parameters to the account.tax compule_all method
        to compute taxes properly in Brazil.
        """
        taxes = base_line["taxes"]._origin
        line = base_line.get("record")
        if not taxes or not line or not line.fiscal_tax_ids:
            return super()._compute_taxes_for_single_line(
                base_line,
                handle_price_include=True,
                include_caba_tags=False,
                early_pay_discount_computation=None,
                early_pay_discount_percentage=None,
            )

        orig_price_unit_after_discount = base_line["price_unit"] * (
            1 - (base_line["discount"] / 100.0)
        )
        price_unit_after_discount = orig_price_unit_after_discount
        # taxes = base_line["taxes"]._origin
        currency = base_line["currency"] or self.env.company.currency_id
        rate = base_line["rate"]

        if early_pay_discount_computation in ("included", "excluded"):
            remaining_part_to_consider = (100 - early_pay_discount_percentage) / 100.0
            price_unit_after_discount = (
                remaining_part_to_consider * price_unit_after_discount
            )

        if taxes:
            taxes_res = taxes.with_context(**base_line["extra_context"]).compute_all(
                price_unit_after_discount,
                currency=currency,
                quantity=base_line["quantity"],
                product=base_line["product"],
                partner=base_line["partner"],
                is_refund=base_line["is_refund"],
                handle_price_include=base_line["handle_price_include"],
                include_caba_tags=include_caba_tags,
            )

            to_update_vals = {
                "tax_tag_ids": [Command.set(taxes_res["base_tags"])],
                "price_subtotal": taxes_res["total_excluded"],
                "price_total": taxes_res["total_included"],
            }

            if early_pay_discount_computation == "excluded":
                new_taxes_res = taxes.with_context(
                    **base_line["extra_context"]
                ).compute_all(
                    orig_price_unit_after_discount,
                    currency=currency,
                    quantity=base_line["quantity"],
                    product=base_line["product"],
                    partner=base_line["partner"],
                    is_refund=base_line["is_refund"],
                    handle_price_include=base_line["handle_price_include"],
                    include_caba_tags=include_caba_tags,
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
                for tax_res, new_tax_res in zip(
                    taxes_res["taxes"], new_taxes_res["taxes"], strict=False
                ):
                    delta_tax = new_tax_res["amount"] - tax_res["amount"]
                    tax_res["amount"] += delta_tax
                    to_update_vals["price_total"] += delta_tax

            tax_values_list = []
            for tax_res in taxes_res["taxes"]:
                tax_amount = tax_res["amount"] / rate
                if self.company_id.tax_calculation_rounding_method == "round_per_line":
                    tax_amount = currency.round(tax_amount)
                tax_rep = self.env["account.tax.repartition.line"].browse(
                    tax_res["tax_repartition_line_id"]
                )
                tax_values_list.append(
                    {
                        **tax_res,
                        "tax_repartition_line": tax_rep,
                        "base_amount_currency": tax_res["base"],
                        "base_amount": currency.round(tax_res["base"] / rate),
                        "tax_amount_currency": tax_res["amount"],
                        "tax_amount": tax_amount,
                    }
                )

        else:
            price_subtotal = currency.round(
                price_unit_after_discount * base_line["quantity"]
            )
            to_update_vals = {
                "tax_tag_ids": [Command.clear()],
                "price_subtotal": price_subtotal,
                "price_total": price_subtotal,
            }
            tax_values_list = []

        return to_update_vals, tax_values_list

    @api.model
    def _add_tax_details_in_base_line(self, base_line, company, rounding_method=None):
        """
        Override to inject Brazilian fiscal tax amounts into the tax details.

        In Odoo 18, _sync_tax_lines uses _add_tax_details_in_base_line to compute
        tax line amounts via the standard _get_tax_details path, which does NOT know
        about Brazilian fiscal specifics (ICMS 'por dentro', PIS/COFINS computed by
        the fiscal module, etc.).

        The BR module overrides _sync_invoice and _compute_needed_terms to use BR
        fiscal amounts. For the journal entry to balance, the tax lines must also use
        the same BR fiscal amounts. This override replaces the standard Odoo amounts
        with the Brazilian fiscal computation results.
        """
        super()._add_tax_details_in_base_line(base_line, company, rounding_method)

        line = base_line.get("record")
        if not line or not hasattr(line, "fiscal_operation_line_id"):
            return
        if not line.fiscal_operation_line_id:
            return

        # Obtain the fiscal taxes via map_fiscal_taxes (same as
        # _compute_fiscal_tax_ids). We avoid line.fiscal_tax_ids because it
        # may be stale/empty for stored records when precompute ran before
        # partner_id was resolved via account.move.line._inherits.
        mapping_result = line.fiscal_operation_line_id.map_fiscal_taxes(
            company=company,
            partner=line.partner_id,
            product=line.product_id,
            ncm=line.ncm_id,
            nbm=line.nbm_id,
            nbs=line.nbs_id,
            cest=line.cest_id,
            city_taxation_code=line.city_taxation_code_id,
            service_type=line.service_type_id,
            ind_final=line.ind_final,
        )
        fiscal_taxes_set = self.env["l10n_br_fiscal.tax"]
        for tax in mapping_result.get("taxes", {}).values():
            fiscal_taxes_set |= tax

        if not fiscal_taxes_set:
            return

        account_taxes_by_domain = {
            tax.id: tax.tax_group_id.fiscal_tax_group_id.tax_domain
            for tax in base_line["tax_ids"]._origin
        }
        rate = base_line["rate"]
        is_refund = base_line.get("is_refund", False)
        repartition_field = (
            "refund_repartition_line_ids"
            if is_refund
            else "invoice_repartition_line_ids"
        )

        # Map tax domains to their stored value/base field names.
        # Most domains follow the pattern {domain}_value / {domain}_base, but some
        # (e.g. icmssn) use non-standard names like icmssn_credit_value.
        DOMAIN_VALUE_FIELD = {"icmssn": "icmssn_credit_value"}

        # Track which domains have already had their amount set to avoid double-counting
        # when multiple Odoo account taxes map to the same BR fiscal domain.
        domains_set = set()

        # Replace each standard Odoo tax amount with the BR fiscal amount.
        # We use stored line fields (e.g. line.icms_value, line.pis_value) instead of
        # calling compute_taxes() again, because compute_taxes() may return incorrect
        # amounts (e.g. ICMS without reduction when the operation line has no reduction
        # tax definition). The stored fields are computed by _compute_fiscal_amounts
        # using the correct per-operation-line tax definitions.
        for tax_data in base_line["tax_details"]["taxes_data"]:
            tax = tax_data["tax"]
            tax_domain = account_taxes_by_domain.get(tax.id)
            if not tax_domain:
                continue
            # Only set amounts for taxes that have repartition lines with type='tax'
            # and factor >= 0 (non-reverse-charge). Taxes without such lines would
            # cause IndexError in _distribute_delta_amount_smoothly.
            tax_reps = tax[repartition_field].filtered(
                lambda x: x.repartition_type == "tax" and x.factor >= 0.0
            )
            if not tax_reps:
                continue
            # Only the first Odoo tax per domain gets the BR fiscal amount.
            # Additional taxes for the same domain (e.g. reporting-only taxes) get 0.
            if tax_domain not in domains_set:
                domains_set.add(tax_domain)
                value_field = DOMAIN_VALUE_FIELD.get(tax_domain, f"{tax_domain}_value")
                fiscal_amount = getattr(line, value_field, 0.0)
                fiscal_base = getattr(line, f"{tax_domain}_base", 0.0)
            else:
                fiscal_amount = 0.0
                fiscal_base = 0.0
            tax_data["raw_tax_amount_currency"] = fiscal_amount
            tax_data["raw_tax_amount"] = (
                company.currency_id.round(fiscal_amount / rate) if rate else 0.0
            )
            tax_data["raw_base_amount_currency"] = fiscal_base
            tax_data["raw_base_amount"] = (
                company.currency_id.round(fiscal_base / rate) if rate else 0.0
            )

        # Handle reverse_charge entries for BR deductible taxes.
        # Deductible taxes (e.g. icms_entrada_deductivel) have amount=0 in
        # their account.tax config and rely on the fiscal module for the actual
        # amount. _get_tax_details negates the regular entry's
        # raw_tax_amount_currency for the reverse_charge entry, but since the
        # deductible tax's regular entry = 0, the reverse_charge also stays 0.
        # We set it here so that the standard
        # _add_accounting_data_to_base_line_tax_details mechanism creates the
        # credit line.
        for tax_data in base_line["tax_details"]["taxes_data"]:
            if not tax_data.get("is_reverse_charge"):
                continue
            tax = tax_data["tax"]
            tax_domain = account_taxes_by_domain.get(tax.id)
            if not tax_domain:
                continue
            value_field = DOMAIN_VALUE_FIELD.get(tax_domain, f"{tax_domain}_value")
            fiscal_amount = getattr(line, value_field, 0.0)
            tax_data["raw_tax_amount_currency"] = -fiscal_amount
            tax_data["raw_tax_amount"] = (
                company.currency_id.round(-fiscal_amount / rate) if rate else 0.0
            )

        # Update total_excluded and total_included to match the BR fiscal
        # amounts. Use stored line fields for consistency with _sync_invoice
        # and _compute_fiscal_amounts. br_net = price minus all taxes that
        # create separate journal lines (included taxes) and minus withholding
        # taxes (which reduce the receivable but don't create lines).
        # ICMS relief (desoneração) also reduces both net and total amounts.
        price = line.price_unit * line.quantity - line.discount_value
        icms_relief = getattr(line, "icms_relief_value", 0.0) or 0.0
        br_net = (
            price - line.amount_tax_included - line.amount_tax_withholding - icms_relief
        )
        br_total = price + line.amount_tax_not_included - icms_relief

        base_line["tax_details"]["raw_total_excluded_currency"] = br_net
        base_line["tax_details"]["raw_total_excluded"] = (
            company.currency_id.round(br_net / rate) if rate else 0.0
        )
        base_line["tax_details"]["raw_total_included_currency"] = br_total
        base_line["tax_details"]["raw_total_included"] = (
            company.currency_id.round(br_total / rate) if rate else 0.0
        )

    @api.model
    def _prepare_tax_lines(self, base_lines, company, tax_lines=None):
        """Override to use fiscal tax group name for Brazilian tax lines.

        In v17, compute_all() was overridden to return fiscal_group.name
        (e.g. 'COFINS') instead of account.tax.name (e.g. 'COFINS Saída').
        In v18, _prepare_tax_lines sets tax_line['name'] = tax.name directly.
        This override restores the v17 naming by using fiscal_tax_group_id.name.
        """
        result = super()._prepare_tax_lines(base_lines, company, tax_lines)

        # Collect all repartition line IDs from both add and update lists
        rep_ids = set()
        for item in result.get("tax_lines_to_add", []):
            rep_id = item.get("tax_repartition_line_id")
            if rep_id:
                rep_ids.add(rep_id)
        for _tl, grouping_key, _amounts in result.get("tax_lines_to_update", []):
            rep_id = grouping_key.get("tax_repartition_line_id")
            if rep_id:
                rep_ids.add(rep_id)
        if not rep_ids:
            return result

        # Build map: rep_line_id -> fiscal tax group name
        rep_lines = self.env["account.tax.repartition.line"].browse(list(rep_ids))
        name_by_rep_id = {}
        for rep_line in rep_lines:
            group_name = rep_line.tax_id.tax_group_id.fiscal_tax_group_id.name
            if group_name:
                name_by_rep_id[rep_line.id] = group_name

        if not name_by_rep_id:
            return result

        for item in result.get("tax_lines_to_add", []):
            rep_id = item.get("tax_repartition_line_id")
            if rep_id in name_by_rep_id:
                item["name"] = name_by_rep_id[rep_id]

        for _tl, grouping_key, amounts in result.get("tax_lines_to_update", []):
            rep_id = grouping_key.get("tax_repartition_line_id")
            if rep_id in name_by_rep_id:
                amounts["name"] = name_by_rep_id[rep_id]

        return result

    @api.model
    def _prepare_tax_totals(
        self, base_lines, currency, tax_lines=None, is_company_currency_requested=False
    ):
        res = super()._prepare_tax_totals(
            base_lines, currency, tax_lines, is_company_currency_requested
        )
        amount_total = res["amount_total"]

        for line in base_lines:
            if line.get("record") and hasattr(
                line["record"], "fiscal_operation_line_id"
            ):
                amount_total = line["record"]._get_total_for_tax_totals()
                break

        res["formatted_amount_total"] = formatLang(
            self.env,
            amount_total,
            currency_obj=currency,
        )

        return res
