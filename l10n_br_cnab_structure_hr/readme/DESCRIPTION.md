Bridge between `l10n_br_cnab_structure` and `hr`. It makes the CNAB payment
rules with "Employee" as partner type match payees that are the work contact
(`work_contact_id`) of an `hr.employee`, so registering the employee in HR is
enough and the `employee` flag of the partner does not need to be set.

The module is installed automatically when both `l10n_br_cnab_structure` and
`hr` are installed. The base CNAB modules do not depend on `hr`.
