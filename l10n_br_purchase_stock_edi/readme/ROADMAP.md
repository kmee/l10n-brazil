- Lots and expiry dates declared by the document (`rastro` of the NF-e) are not
  proposed on the receipt yet: the import does not read them.
- Receipts as a source of the reconciliation screen of `l10n_br_purchase_edi`.
- Receipt created from the document for a stockable product bought without an
  order, and the mark of a line without stock entry.
- The divergence is not stored, so the filters of the lists read the lines
  linked to an order line; measure it on a large database before storing and
  indexing it.
