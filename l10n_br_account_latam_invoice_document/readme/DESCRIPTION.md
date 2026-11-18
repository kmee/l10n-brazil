Compatibility between `l10n_br_account` and `l10n_latam_invoice_document`,
installed automatically when both are present (for example when the Odoo
`l10n_br` module is installed for a Brazilian company).

On a Brazilian company the Latin American document type of an invoice comes
from its fiscal document type, and posting does not ask for the manual
document number, whose numbering is done by `l10n_br_fiscal`. Other
companies keep the standard Latin American validation.

`l10n_br_account` does not depend on `l10n_latam_invoice_document`: the
overrides of its methods are kept in this module, which depends on both, so
they always load after them.
