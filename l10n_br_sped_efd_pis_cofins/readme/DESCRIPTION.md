## EFD Contribuições (PIS/COFINS)

This module generates (and imports) the Brazilian **EFD Contribuições
(PIS/COFINS)** digital file from Odoo transactions, on top of the abstract
`l10n_br_sped_base` framework. It shares the same engine as
`l10n_br_sped_efd_icms_ipi`: each register inherits its generated abstract spec
(layout 006) and is populated recursively from Odoo data between `DT_INI` and
`DT_FIN`.

The register structure is **machine-generated** by
[sped-extractor](https://github.com/akretion/sped-extractor) and must not be
hand-edited.

## Coverage

Populated automatically from Odoo:

- **Bloco 0**: 0000, 0110 (regime), 0140 (establishment), 0150, 0190, 0200
- **Bloco C**: C010, C100, C170 (goods, with PIS/COFINS per item)
- **Bloco D**: D010, D100 (transport CT-e)
- **Bloco M**: M100/M200/M210 (PIS) and M500/M600/M610 (COFINS) — the
  assessment, computed from the period documents (a baseline; the precise
  PIS/COFINS treatment is CST-driven and is refined by the accountant)
- **Bloco 9**: generated automatically by the framework

Kept as fillable stubs (no automatic Odoo source — entered manually or via SPED
import): **Bloco F** (other revenues/operations not modelled as fiscal
documents), **Bloco 1** (judicial processes, cross-period credit control), the
D101/D105 freight credits and the assessment adjustments.

**Tax reform note:** EFD Contribuições covers PIS/COFINS, which are extinct from
2027 (replaced by CBS). This obligation therefore applies only to periods up to
2026; the module has a bounded useful life.
