Link between the fiscal document import by file or access key
(`l10n_br_fiscal_dfe_import`) and the accounting (`l10n_br_account`). It
installs itself when both modules are present.

It adds the Generate Invoice button to the imported document, which creates the
vendor bill only when every line was resolved, and makes the attachments sent
from the vendor bills list use the new import window.
