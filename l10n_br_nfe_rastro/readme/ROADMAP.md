- The groups are filled by the picking invoicing wizard. Invoices created
  in other ways (from a sale order, by hand) can call
  `account.move.line._fill_nfe40_rastro()` or have the groups typed in.
- The aggregation code (`cAgreg`) is not filled automatically.
- Importing an incoming NF-e keeps its lots on the fiscal document line,
  but does not create the stock lots of the receipt.
