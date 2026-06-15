## EFD ICMS/IPI (SPED Fiscal)

This module generates (and imports) the Brazilian **EFD ICMS/IPI (SPED Fiscal)**
digital file from Odoo transactions, on top of the abstract `l10n_br_sped_base`
framework. Each SPED register inherits the generated abstract spec and is
populated recursively from Odoo data between the declaration dates `DT_INI` and
`DT_FIN`. See `l10n_br_sped_base` for how the mapping engine works.

The register structure is **machine-generated** by
[sped-extractor](https://github.com/akretion/sped-extractor) for layout 020
(in force since 2026-01-01, Ato COTEPE/ICMS 79/2025, Guia Prático v3.2.x) and
must not be hand-edited. The mapping from Odoo transactions is **work in
progress** and is being delivered block by block, prioritizing the industry
profile (Bloco 0, C, E, K). Registers without an automated mapping yet can be
completed manually inside Odoo or by importing an existing SPED file.

**Tax reform note:** EFD ICMS/IPI carries ICMS/IPI only. On layout 020 the new
reform taxes (CBS, IBS, IS) are explicitly excluded from the EFD amounts; this
module therefore maps ICMS/IPI values only.

> Bootstrap status: only register 0000 is wired so far, to validate the module
> against `l10n_br_sped_base` on Odoo 18.0. The full layout-020 spec and the
> block mappings are added in the following phases.
