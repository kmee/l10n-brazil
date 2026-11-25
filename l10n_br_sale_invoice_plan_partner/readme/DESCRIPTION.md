Glue between `l10n_br_sale_invoice_plan` and `sale_invoice_plan_partner`.

When the invoice plan of a sales order splits it among payers, each
invoice goes to its payer. The fiscal data of the order lines (fiscal
operation line, CFOP, taxes, final consumer indicator, withholdings) was
computed for the customer of the order, so it is not copied to the
invoice of another payer: the invoice lines compute it for the payer, as
if the payer had ordered its share directly. Without this, an invoice to
an individual would keep the taxpayer operation of a company customer
(no DIFAL, wrong final consumer indicator, company withholdings).
