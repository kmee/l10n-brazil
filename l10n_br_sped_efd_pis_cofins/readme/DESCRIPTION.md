## EFD Contribuições (PIS/COFINS)

This module generates (and imports) the Brazilian **EFD Contribuições
(PIS/COFINS)** digital file from Odoo transactions, on top of the abstract
`l10n_br_sped_base` framework. It shares the same engine as
`l10n_br_sped_efd_icms_ipi`: each register inherits its generated abstract spec
(layout 006) and is populated recursively from Odoo data between `DT_INI` and
`DT_FIN`.

The register structure is **machine-generated** by
[sped-extractor](https://github.com/akretion/sped-extractor) and must not be
hand-edited. The mapping from Odoo transactions is delivered block by block
(Bloco 0, C and M — the PIS/COFINS assessment).

**Tax reform note:** EFD Contribuições covers PIS/COFINS, which are extinct from
2027 (replaced by CBS). This obligation therefore applies only to periods up to
2026; the module has a bounded useful life.
