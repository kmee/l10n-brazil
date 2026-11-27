Demo data of the purchases link (`l10n_br_purchase_edi`) and of the stock link
(`l10n_br_purchase_stock_edi`) of the import of fiscal documents.

The documents of the demo are sample NF-e files, imported by the same service
that a person uses, so the module needs the NF-e reader (`l10n_br_nfe`). It is
kept apart from the modules of the links, which do not depend on the type of the
document that was imported and must install with their demo data in a database
that has no NF-e. It installs itself when the links and `l10n_br_nfe` are present.
