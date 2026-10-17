# Copyright (C) 2026 - KMEE (<http://kmee.com.br>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""Helpers for boleto barcode (44 digits) and linha digitavel (47/48 digits).

Layout FEBRABAN of the banking barcode (44 digits)::

    bank(3) currency(1) DV(1) due factor(4) value(10) free field(25)

The linha digitavel of a banking boleto (47 digits) holds the same data
rearranged in 3 fields with their own mod 10 DV, plus the general DV and the
factor/value block.  Utility (concessionaria) boletos use 48 digits: four blocks
of 11 digits, each followed by its own DV, that build a 44 digit barcode.
"""

import re
from decimal import Decimal

_NON_DIGIT_SEPARATORS = re.compile(r"[\s.\-]")


def clean_digits(value):
    """Strip spaces, dots and hyphens. Returns the string (maybe not numeric)."""
    return _NON_DIGIT_SEPARATORS.sub("", value or "")


def mod10(number):
    """Mod 10 DV (weights 2,1 from the right, digits of products summed)."""
    total = 0
    weight = 2
    for digit in reversed(number):
        prod = int(digit) * weight
        total += prod // 10 + prod % 10
        weight = 1 if weight == 2 else 2
    return (10 - total % 10) % 10


def mod11_barcode(number):
    """Mod 11 DV of the banking barcode (weights 2..9; 0, 10, 11 become 1)."""
    total = 0
    weight = 2
    for digit in reversed(number):
        total += int(digit) * weight
        weight = 2 if weight == 9 else weight + 1
    dv = 11 - total % 11
    return 1 if dv in (0, 10, 11) else dv


def mod11_utility(number):
    """Mod 11 DV of utility blocks (weights 2..9; remainder 0 or 1 gives 0)."""
    total = 0
    weight = 2
    for digit in reversed(number):
        total += int(digit) * weight
        weight = 2 if weight == 9 else weight + 1
    rest = total % 11
    if rest in (0, 1):
        return 0
    return 11 - rest


def _utility_dv(number, reference):
    """Utility DV: mod 10 when value reference is 6 or 7, mod 11 otherwise."""
    if reference in ("6", "7"):
        return mod10(number)
    return mod11_utility(number)


def is_valid_barcode(barcode):
    """True if ``barcode`` is a 44 digit code with a valid general DV."""
    if not barcode or len(barcode) != 44 or not barcode.isdigit():
        return False
    if barcode[0] == "8":
        # Utility/tax: general DV at position 4 (index 3)
        body = barcode[:3] + barcode[4:]
        return int(barcode[3]) == _utility_dv(body, barcode[2])
    return int(barcode[4]) == mod11_barcode(barcode[:4] + barcode[5:])


def barcode_from_digitable_line(line):
    """Convert 47 (banking) or 48 (utility) digits into the 44 digit barcode.

    Returns False when the length is not 47/48 or it is not numeric.
    The result is not guaranteed to have a valid DV, use ``is_valid_barcode``.
    """
    if not line or not line.isdigit():
        return False
    if len(line) == 47:
        return (
            line[0:4] + line[32] + line[33:47] + line[4:9] + line[10:20] + line[21:31]
        )
    if len(line) == 48:
        return "".join(line[i : i + 11] for i in range(0, 48, 12))
    return False


def digitable_line_from_barcode(barcode):
    """Build the linha digitavel of a barcode (False if not a 44 digit code).

    Banking barcodes give the 47 digit line (3 fields with mod 10 DV). Utility
    barcodes (prefix 8) give the 48 digit line: four blocks of 11 digits, each
    followed by its own DV (mod 10 when the value reference, 3rd digit, is 6 or
    7, mod 11 otherwise), as required by CNAB segment O.
    """
    if not barcode or len(barcode) != 44 or not barcode.isdigit():
        return False
    if barcode[0] == "8":
        reference = barcode[2]
        blocks = (barcode[i : i + 11] for i in range(0, 44, 11))
        return "".join(block + str(_utility_dv(block, reference)) for block in blocks)
    field1 = barcode[0:4] + barcode[19:24]
    field2 = barcode[24:34]
    field3 = barcode[34:44]
    return (
        field1
        + str(mod10(field1))
        + field2
        + str(mod10(field2))
        + field3
        + str(mod10(field3))
        + barcode[4]
        + barcode[5:19]
    )


def normalize_barcode(value):
    """Normalize user input into ``(barcode, digitable_line, is_valid)``.

    ``value`` may be a 44 digit barcode or a 47/48 digit linha digitavel, with
    spaces, dots or hyphens. When the value is invalid (bad length, non numeric
    or wrong DV) ``barcode`` is the cleaned input unchanged and ``is_valid`` is
    False, so the caller can keep the data and block later with a clear message.
    """
    cleaned = clean_digits(value)
    if not cleaned:
        return False, False, False
    if len(cleaned) in (47, 48):
        barcode = barcode_from_digitable_line(cleaned)
        if barcode and is_valid_barcode(barcode):
            return barcode, cleaned, True
        return cleaned, False, False
    if is_valid_barcode(cleaned):
        return cleaned, digitable_line_from_barcode(cleaned), True
    return cleaned, False, False


def barcode_value(barcode):
    """Value (Decimal, in currency units) written in a 44 digits barcode.

    Banking boleto: positions 10-19 (zero means "any value"). Utility and tax
    barcode (starts with 8): positions 5-15, only when the value identifier
    (3rd digit) says it is the effective value (6 and 8). Returns ``None``
    when the barcode has no value, so the caller must not validate amounts.
    """
    code = clean_digits(barcode)
    if len(code) != 44 or not code.isdigit():
        return None
    if code[0] == "8":
        raw = code[4:15] if code[2] in ("6", "8") else ""
    else:
        raw = code[9:19]
    if not raw or not int(raw):
        return None
    return Decimal(int(raw)) / 100
