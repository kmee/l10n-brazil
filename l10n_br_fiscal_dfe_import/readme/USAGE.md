**Import files**

1. Open Fiscal > Documents > NF-e > Import.
2. Upload one XML, several, or a zip with them and click Import.
3. A single file opens the document; several files open the list of the
   documents created, and the files that were not imported are reported.

A note already imported for the same company opens the existing document. A
note cancelled or denied (by the protocol of the file or by the DF-e inbox) is
refused, and so is a note whose recipient CNPJ is not a company of the
database. Each note goes to the company of its recipient CNPJ.

**Import by access key**

1. Open the same window, fill the access key and click Import.
2. If the complete XML is already in the DF-e inbox, the document is created.
3. If only the summary is available, the window asks for a confirmation to
   register the acknowledgement of the operation (ciência), which releases the
   XML. That event obliges the company to register the final manifestation
   afterwards. The document is created when the complete XML arrives.
4. The acknowledgement is only possible until 10 days after the authorization;
   after that the window asks for the XML file instead.

**Review**

The imported document is born with the inbound fiscal operation suggested from
the CFOP declared by the issuer (on the header and on each line, with the
inbound CFOP of the operation line), without changing the quantities, prices
and taxes of the file. When no operation matches, or the NCM of the file is
not in the registry, a banner tells what to choose. The Imported Documents menu
has a column with the review state and a filter for the documents awaiting
review.

A product that the buyer already mapped for the same supplier (the supplier
code of the product equal to the code of the note) enters resolved, converted
with the factor learned for the same declared unit. A product found only by
internal code, barcode or name is a suggestion: the Confirm Suggestions button
resolves all of them at once. Resolving a line by hand records the mapping
once, so the next note of the supplier already enters resolved.
