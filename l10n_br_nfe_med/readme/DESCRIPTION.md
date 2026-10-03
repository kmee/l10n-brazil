This module reports the medicine group of the NF-e items (group K, `med`)
and enforces the traceability group that the SEFAZ requires for
medicines.

The ANVISA code (`cProdANVISA`), the exemption reason
(`xMotivoIsencao`) and the maximum consumer price (`vPMC`) are set once
on the product and copied to the fiscal document lines of that product.
The values can be changed on each line, and the lines of an incoming
NF-e keep the values of the supplier XML.

The ANVISA code is checked against the layout: 11 or 13 digits, or
`ISENTO` for medicines exempt from registration.

Rule K01-20 (rejection 873) requires the traceability group (`rastro`)
on every item with the medicine group. The module refuses to confirm
such an NF-e without lots, except in the cases listed by the rule:
complementary, adjustment and return NF-e, non presential sales
(`indPres` 2 or 3), incoming NF-e, DANFE type 6 and the CFOP of future
delivery and sale on behalf of a third party (5922, 6922, 5118 to 5120,
6118 to 6120). The lots come from the `l10n_br_nfe_rastro` module.
