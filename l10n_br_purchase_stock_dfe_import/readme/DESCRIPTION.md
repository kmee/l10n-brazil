Link between the fiscal document import (`l10n_br_fiscal_dfe_import`), the
purchase link (`l10n_br_purchase_dfe_import`) and stock
(`l10n_br_purchase_stock`). It installs itself when they are present.

- The receipt move is the origin of an imported document line, together with
  the purchase order line, and appears in the reconciliation screen as a
  source of its own.
- A stockable product bought without an order can have the receipt created from
  the document.
- The lots and expiry dates of the NF-e (the lot group of the file) are
  proposed on the receipt for the operator to review.
- The document line and the bill line are compared with the order and the
  receipt: ordered, received and invoiced quantities, order price, and the
  differences, with tolerances by company. It only warns, nothing is blocked.
