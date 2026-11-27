Link between the import of fiscal documents (`l10n_br_fiscal_edi`), the
purchase link (`l10n_br_purchase_edi`) and stock
(`l10n_br_purchase_stock`). It installs itself when they are present.

- The receipt move is the origin of an imported document line, together with
  the purchase order line, and appears in the reconciliation screen as a
  source of its own.
- A stockable product bought without an order can have the receipt created from
  the document.
- The lots and expiry dates the document declares (`_edi_get_lots` of its
  line, whatever the type of the document) are proposed on the receipt for the
  operator to review.
- The document line and the bill line are compared with the order and the
  receipt: ordered, received and invoiced quantities, order price, and the
  differences, with tolerances by company. It only warns, nothing is blocked.

Demo data: a supplier, orders and sample NF-e files that walk the cycle of
life of the import (the note invoiced, the quotation to match, the note
without order, the lots and the receipt). The notes are imported by the same
service that a person uses, so the demo is loaded only when the demo data was
asked for and the NF-e module (`l10n_br_nfe`) is installed at the moment of
the installation of this module. Without NF-e the module installs with no demo.
