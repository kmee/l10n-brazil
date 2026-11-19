- Purchase requests as a source of the reconciliation, in their own link module.
- The receipt created from a document uses the price of the document as cost;
  the net cost without the recoverable taxes (`stock_cost_unit`) is not
  proposed yet.
- The divergence is not stored, so the filters of the lists read the lines
  linked to an order line; a stored and indexed value is the next step for a
  database with many bills.
- The receipt of a line decided as without order is not taken back if the
  decision is changed afterwards.
