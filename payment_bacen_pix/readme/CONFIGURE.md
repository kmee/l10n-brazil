To configure the provider go to Invoicing -\> Configuration -\> Payment
Providers -\> Pix and fill in:

- **Pix Provider**: the bank that holds the account;
- **Pix Key**: the key that receives the payments, as registered with the PSP;
- **Client ID** and **Client Secret**: the credentials of the application
  created in the developer portal of the bank;
- **Application Key**: only for the Banco do Brasil, the `gw-dev-app-key` of
  the application;
- **Certificate** and **Private Key**: the client certificate in the PEM
  format, required by the PSPs that demand mutual TLS, such as the Banco Inter;
- **Charge Configuration**: the charge registered when the document being paid
  has no payment mode saying which one to use, as in an e-commerce checkout.

The Pix arrangement has two kinds of charge, and the choice belongs to the
merchant, not to the data of the payment:

- the **immediate charge** (`cob`) is a QR code payable until it expires, and
  the expiration can be minutes or days: a charge that stays payable for a week
  is still an immediate charge;
- the **charge with a due date** (`cobv`) is the one that behaves like a boleto:
  it carries fine, interest, discount and rebate, and stays payable for a while
  after the due date.

Each kind, with its terms, is a record of *Pix Charge Configuration*, and the
configuration is picked on the **payment mode** of the document. The provider
only answers for the payments that have no payment mode behind them. A charge
with a due date needs the due date on the transaction, and the Pix arrangement
requires the name, the CPF/CNPJ and the full address of the debtor.

While the provider is in the *Test Mode* state, the sandbox of the PSP is used.

The payment is confirmed either by the notification of the PSP, sent to
`/payment/bacenpix/webhook` and registered with `PUT /webhook/{chave}`, or by
the scheduled action *Pix: Poll the charges waiting for a payment*, which is
disabled by default. The page holding the QR code also polls the charge while
the payer keeps it open.

Pix settles in BRL only: the provider is filtered out of the payment methods
offered to the customer for any other currency.

API reference: <https://bacen.github.io/pix-api>
