After importing a vendor NF-e (**Invoicing > Vendors > Import Fiscal Document**),
the lines of the document keep an origin: the purchase order line they
correspond to, and the state of that origin (pending, suggested, resolved or
without order). The origin is on the *Extra Info* tab of the fiscal line.

- When the supplier declared the order and the item in the file (`xPed` and
  `nItemPed`) and they identify exactly one line of a confirmed order, the
  origin is resolved by itself and the vendor bill is created already linked to
  the order line: the order counts the quantity as invoiced and the bill
  source document gets the order number.
- When the supplier has a single open order line for the product, the origin is
  suggested. Press **Confirm Origins** on the bill to accept the suggestions.
- When there are several candidates, the origin stays pending and the line
  lets you choose the order line.

The vendor bill cannot be posted while a line has a suggested origin or a
pending one with candidates. While the bill is a draft, deciding the origin
later links (or unlinks) the bill line.

**Match with Orders**, on the bill, opens the reconciliation of the document:
its lines, the confirmed order lines with their balance and the quotations of
the supplier. Select the document lines and one order line and press
**Match**. Other buttons:

- **Undo**: the origin goes back to pending.
- **Without Order**: records that there is no order.
- **Open Quotation**: opens the quotation so the buyer confirms it. A quotation
  cannot be matched; once the order is confirmed the line receives the
  suggestion.
- **Create Order from the Document**: creates a draft purchase order with the
  selected lines (supplier, product, quantity and price of the document). It is
  not confirmed; when the buyer confirms it, the line receives the suggestion.

The menu **Purchase > Orders > Match Imported Documents** lists what waits for
a decision, for the buyer.
