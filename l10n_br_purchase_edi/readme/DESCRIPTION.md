Link between the import of vendor fiscal documents (`l10n_br_account_nfe`) and
purchases (`l10n_br_purchase`). It installs itself when both are present.

An imported vendor document has to answer where it came from: a purchase
order, a quotation or nothing. This module keeps the answer on each line of the
document: the purchase order line it corresponds to, and whether that origin is
pending, suggested, resolved, or decided to be without an order. The vendor
bill links each line to its order line, and the order counts what was invoiced.

It also adds a screen that puts the lines of the document next to the open
order lines and the quotations of the same supplier, to match them, create the
order that was missing, or record that there is none.
