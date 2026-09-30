# Copyright 2026 - TODAY Akretion (<https://akretion.com>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Remove CNPJ/CPF mask characters from Brazilian partner vat values.

    res.partner.vat is stored unformatted (without ``.``, ``/`` or ``-``).
    Records created before this change may still hold formatted values, so
    strip the punctuation before the ORM loads the fields that depend on the
    unformatted value.
    """
    cr.execute(
        """
        UPDATE res_partner
           SET vat = regexp_replace(vat, '[./-]', '', 'g')
         WHERE country_id = (SELECT id FROM res_country WHERE code = 'BR')
           AND vat ~ '[./-]'
        """
    )
    _logger.info(
        "l10n_br_base: stripped the mask of %s Brazilian vat values", cr.rowcount
    )
