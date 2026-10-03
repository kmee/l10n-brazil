This module fills the traceability group of the NF-e items (group I80,
`rastro`) from the stock lots, and checks it before the NF-e is issued.

The group was created by NT 2016.002 for products subject to sanitary
regulation or recall: medicines, beverages, bottled water, veterinary and
agricultural products and so on. Each item can carry up to 500 lots, each
one with its number, quantity, manufacturing date and expiration date.

When an invoice is created from a delivery (picking invoicing), each lot
shipped becomes one traceability group of the invoice line:

- lot number: the lot name;
- quantity: the quantity of the lot in the invoice line unit;
- manufacturing date: the lot production date;
- expiration date: the lot expiration date.

Both dates are read as calendar dates in the user time zone.

Before the NF-e is confirmed the module refuses the data the SEFAZ would
reject: missing lot number or dates, more than 500 lots, a manufacturing
date after the issue date (rule I83-10, rejection 877) and an expiration
date before the manufacturing date (rule I84-10, rejection 870).

The lots of an incoming NF-e are kept on the imported lines, and the
groups can be edited by hand on the invoice line and on the fiscal
document line (Traceability tab).
