Payment Provider: Pix, through the API standardized by the Brazilian Central
Bank.

The customer pays with a QR code (or with the copy and paste payload) generated
on the account of the merchant, either as an immediate charge (`cob`), payable
until it expires, or as a charge with a due date (`cobv`), which accepts fine,
interest and discount and stays payable after it is due. Which one to register
is told by the Pix charge configuration of the payment mode. The API of the
charges is the same for every PSP: the bank is chosen in the configuration of
the provider, which only changes the base URL, the way the OAuth token is
obtained and whether a client certificate is required.

Supported PSPs: Banco do Brasil and Banco Inter.

The name, the document and the address of the payer are redacted before any
payload, response or notification is logged: the log of a gateway has no need
for them.
