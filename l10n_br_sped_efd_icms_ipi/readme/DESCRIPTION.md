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

## Coverage

The full layout-020 register structure (all blocks) is in place. The following
registers are populated automatically from Odoo:

- **Bloco 0**: 0000, 0002, 0005, 0100, 0150, 0190, 0200, 0220, 0400, 0450
- **Bloco C**: C100, C110, C170, C190 (goods); C500, C590 (energy/utilities)
- **Bloco D**: D100, D190 (CT-e transport)
- **Bloco E**: E100/E110 (ICMS), E200/E210 (ICMS-ST per UF), E500/E510/E520 (IPI)
- **Bloco H**: H005, H010 (inventory)
- **Bloco K**: K010, K100, K200; K230/K235 (production — soft dependency on `mrp`)
- **Bloco 1**: 1010
- **Bloco 9**: generated automatically by the framework

Registers that depend on data Odoo does not model are kept as concrete stubs to
be filled in manually (or via SPED file import): the assessment adjustments
(E111/E116, E220-E250, E530), Bloco G (CIAP) and C113 (referenced documents).
