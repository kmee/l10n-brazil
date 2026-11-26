Link between the import of vendor fiscal documents, the purchase link
(`l10n_br_purchase_edi`) and stock (`l10n_br_purchase_stock`). It installs
itself when they are present.

- The receipt move is the origin of an imported document line, together with
  the purchase order line.
- The receipt is filled by the document: the quantity the document declares is
  proposed on the receipt for the operator to review.
- The document line and the bill line are compared with the order and the
  receipt: ordered, received and invoiced quantities, order price, and the
  differences, with tolerances by company. It only warns, nothing is blocked.
