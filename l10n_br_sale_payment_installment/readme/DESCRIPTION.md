When a customer pays a sales order in installments and the company charges the
interest (module *Sale Payment Installments*), the generic behaviour is to add a
surcharge line to the order.

A Brazilian fiscal document has no place for such a line: on the NF-e and the
NFC-e, amounts the seller charges on top of the goods are *other costs*
(`vOutro`), spread over the items, and they are part of the tax bases.

With this module, on a sales order that has a fiscal operation:

- the interest is spread over the other costs of the goods, by gross amount,
  instead of becoming a line;
- the other costs are set so that the total of the order grows by exactly the
  interest the payer was shown, including the taxes computed on other costs
  (IPI);
- other costs the order already had are kept, whether the company informs them
  by line or by total;
- the amounts follow the order to the invoice and to the fiscal document.

Orders with services taxed by ISS do not offer the options with interest
charged by the company: the NFS-e has no field for other costs and they are not
part of the ISS base.
