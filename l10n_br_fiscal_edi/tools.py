# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from dataclasses import dataclass
from datetime import date, datetime, timezone

from odoo import fields


def tax_authority_date_to_utc(value):
    """Convert a date of the tax authority answer into a UTC naive string.

    The answer carries the local time with an offset (for example
    2026-10-02T10:15:00-03:00, or -04:00 in MT/AM), but the Datetime fields keep
    naive UTC. A value without offset is kept as it is.
    """
    if not value:
        return False
    if not isinstance(value, datetime):
        if hasattr(value, "to_datetime"):  # xsdata XmlDateTime
            value = value.to_datetime()
        else:
            value = datetime.fromisoformat(value)
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return fields.Datetime.to_string(value)


# Context key of the import: it never creates a product, a unit, an NCM, a CEST or a
# CFOP that the file mentions and the database does not have.
EDI_IMPORT_NO_CREATE = "edi_import_no_create"

# Context key of the creation of the document: a partner is matched by its CNPJ or CPF
# and never by its name. Only a file that carries neither (final consumer, foreigner)
# may match by name, and the document says so.
EDI_IMPORT_PARTNER_BY_VAT = "edi_import_partner_by_vat"


@dataclass(frozen=True)
class EdiParsedFile:
    """What a reader found in a fiscal file, before anything is created."""

    reader: str  # "nfe" | "cte" | "nfse" | "mdfe"
    document_type_code: str  # "55" | "57" | "SE" | "58"
    access_key: str  # only digits, 44 or 50
    issuer_vat: str  # only digits
    # ((role, digits), ...) in priority order; role in
    # ("recipient", "taker", "issuer")
    company_vats: tuple
    status: str  # "authorized" | "cancelled" | "denied" | "unknown"
    status_code: str  # cStat or ""
    binding: object  # what the reader needs in _edi_import_create
    file_name: str
    content: bytes


@dataclass(frozen=True)
class EdiInstallment:
    number: str  # "001", "002"
    date_due: date
    amount: float  # positive, in the currency of the document


@dataclass(frozen=True)
class EdiPayment:
    means: str  # tPag; "" = unknown; "90" = no payment
    amount: float
    term: str  # "cash" | "installments"  (indPag 0 / 1)
    description: str = ""  # xPag when tPag = "99"


@dataclass(frozen=True)
class EdiLot:
    name: str
    quantity: float  # in the unit declared by the line
    date_manufacture: date | None
    date_expiry: date | None
