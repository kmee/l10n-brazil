# Copyright 2023 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

# The Pix API is standardized by the Brazilian Central Bank, so the payload of
# the charges is the same for every PSP. What changes from one PSP to another is
# the base URL, the way the OAuth token is obtained and whether mutual TLS is
# required. See https://bacen.github.io/pix-api.
PSP_CONFIG = {
    "bb": {
        "name": "Banco do Brasil",
        "token_url": {
            "test": "https://oauth.sandbox.bb.com.br/oauth/token",
            "prod": "https://oauth.bb.com.br/oauth/token",
        },
        "api_url": {
            "test": "https://api.sandbox.bb.com.br/pix/v2",
            "prod": "https://api-pix.bb.com.br/pix/v2",
        },
        # The BB gateway expects its application key on every call.
        "app_key_param": "gw-dev-app-key",
        # The credentials go in the Basic authorization header of the token
        # request, as required by the BB.
        "token_auth": "basic",
        "mutual_tls": False,
    },
    "inter": {
        "name": "Banco Inter",
        "token_url": {
            "test": "https://cdpj-sandbox.partners.uatinter.co/oauth/v2/token",
            "prod": "https://cdpj.partners.bancointer.com.br/oauth/v2/token",
        },
        "api_url": {
            "test": "https://cdpj-sandbox.partners.uatinter.co/pix/v2",
            "prod": "https://cdpj.partners.bancointer.com.br/pix/v2",
        },
        "app_key_param": None,
        # The credentials go in the body of the token request.
        "token_auth": "body",
        "mutual_tls": True,
    },
}

# The scopes needed to manage the charges and read the received payments.
OAUTH_SCOPE = "cob.read cob.write cobv.read cobv.write pix.read"

# Pix settles in BRL only.
SUPPORTED_CURRENCIES = ["BRL"]

# Mapping of the status of a charge to the state of the transaction.
# See the `StatusCobranca` schema of the Pix API.
PAYMENT_STATUS_MAPPING = {
    "pending": ("ATIVA",),
    "done": ("CONCLUIDA",),
    "cancel": ("REMOVIDA_PELO_USUARIO_RECEBEDOR", "REMOVIDA_PELO_PSP"),
}

# The number of seconds before an unpaid charge expires, when the provider does
# not define it.
DEFAULT_EXPIRATION = 3600

# The modes of fine, interest and discount of a charge with a due date.
# See the `Multa`, `Juros` and `Desconto` schemas of the Pix API.
FINE_MODES = [
    ("1", "Fixed amount"),
    ("2", "Percentage"),
]
INTEREST_MODES = [
    ("1", "Amount per calendar day"),
    ("2", "Percentage per calendar day"),
    ("3", "Percentage per month, calendar days"),
    ("4", "Percentage per year, calendar days"),
    ("5", "Amount per business day"),
    ("6", "Percentage per business day"),
    ("7", "Percentage per month, business days"),
    ("8", "Percentage per year, business days"),
]
DISCOUNT_MODES = [
    ("1", "Fixed amount until the given date"),
    ("2", "Percentage until the given date"),
]

# How many days a charge with a due date stays payable after it is due.
DEFAULT_VALIDITY_AFTER_DUE_DATE = 30
