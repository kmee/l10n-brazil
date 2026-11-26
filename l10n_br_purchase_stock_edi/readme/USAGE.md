When the origin of a line of the imported document is decided, the line also
points to the receipt move of the order line if there is a single candidate:
the received and not yet invoiced move first, otherwise the only one still to
come. Returns are never candidates. The receipts show on the vendor bill.

On the draft vendor bill, **Fill Receipt from the Document** puts on the
receipt the quantity the document declares, for the receipts that nobody
picked yet. The operator reviews and validates the receipt; nothing is
validated by the button.

The lines of the document and of the bill show the ordered and received
quantity, the order price and the differences. A line out of the tolerances of
the company (Bill Price Tolerance and Bill Quantity Tolerance, in percentage,
zero by default, in the company form) is marked as divergent, the document and
the bill get a badge, and the lists have a filter. A bill issued before the
receipt is awaiting the receipt, which is not a divergence.
