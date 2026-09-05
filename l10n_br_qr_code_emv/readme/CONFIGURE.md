1. Register the Pix key on the invoice-issuing company's partner. With
   `l10n_br_account` installed, this is under the *Invoicing* tab (*Pix Keys*);
   otherwise it is on the bank account form itself, in the *Brazilian Instant
   Payment Keys (PIX)* section, which only shows once the account's company has
   Brazilian localization. Optionally link the key to the specific bank account
   that should receive the payment; otherwise the partner's first key is used.
2. The partner issuing the invoice needs a City: Pix requires it as Merchant City.
3. In *Accounting/Invoicing > Configuration > Settings > Customer Payments*, enable
   *QR Codes*.
4. Nothing else to configure: the invoice picks the EMV QR code automatically once
   eligible. If it does not appear, open the invoice's *Other Info* tab and check the
   *QR Code* field for the specific error message.
