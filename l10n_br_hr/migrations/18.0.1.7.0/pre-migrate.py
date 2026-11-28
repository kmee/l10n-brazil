# Copyright 2026 Akretion - Raphaël Valyi <raphael.valyi@akretion.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from erpbrasil.base import misc
from erpbrasil.base.fiscal import cnpj_cpf
from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)


def _unique_standalone_partner(env, vat):
    """Return the only active person, not a user nor a work contact, with the vat."""
    env.cr.execute(
        """
        SELECT p.id FROM res_partner p
         WHERE regexp_replace(coalesce(p.vat, ''), '\\D', '', 'g') = %s
           AND p.active AND NOT coalesce(p.is_company, false)
           AND NOT EXISTS (SELECT 1 FROM res_users u WHERE u.partner_id = p.id)
           AND NOT EXISTS (SELECT 1 FROM hr_employee e WHERE e.work_contact_id = p.id)
        """,
        (vat,),
    )
    rows = env.cr.fetchall()
    return rows[0][0] if len(rows) == 1 else None


def _salvage_vat(env, column):
    if not openupgrade.column_exists(env.cr, "hr_employee", column):
        return
    env.cr.execute(
        f"""
        SELECT e.id, e.work_contact_id, e.{column}, p.vat
          FROM hr_employee e
          JOIN res_partner p ON p.id = e.work_contact_id
         WHERE e.{column} IS NOT NULL
           AND e.{column} != ''
        """
    )
    salvaged = skipped = 0
    for employee_id, partner_id, legacy_value, partner_vat in env.cr.fetchall():
        if partner_vat:
            skipped += 1
            continue
        clean_value = misc.punctuation_rm(legacy_value)
        if not cnpj_cpf.validar(clean_value):
            skipped += 1
            _logger.info(
                "l10n_br_hr: legacy hr_employee(%s).%s %r is not a valid "
                "CNPJ/CPF, not salvaged to res_partner(%s).vat",
                employee_id,
                column,
                legacy_value,
                partner_id,
            )
            continue
        # a standalone contact registered for the same person becomes the
        # work contact instead of duplicating the CPF
        standalone_id = _unique_standalone_partner(env, clean_value)
        if standalone_id:
            env.cr.execute(
                "UPDATE hr_employee SET work_contact_id = %s WHERE id = %s",
                (standalone_id, employee_id),
            )
            salvaged += 1
            continue
        env.cr.execute(
            "SELECT 1 FROM res_partner WHERE vat = %s AND id != %s LIMIT 1",
            (clean_value, partner_id),
        )
        if env.cr.fetchone():
            skipped += 1
            _logger.info(
                "l10n_br_hr: legacy hr_employee(%s).%s %r already used by "
                "another partner, not salvaged to res_partner(%s).vat",
                employee_id,
                column,
                legacy_value,
                partner_id,
            )
            continue
        env.cr.execute(
            """
            UPDATE res_partner
               SET vat = %(vat)s,
                   cnpj_cpf_stripped = %(vat)s,
                   write_uid = %(uid)s,
                   write_date = NOW() AT TIME ZONE 'UTC'
             WHERE id = %(id)s
            """,
            {"vat": clean_value, "uid": env.uid, "id": partner_id},
        )
        salvaged += 1
    _logger.info(
        "l10n_br_hr: salvaged %s legacy hr_employee.%s values into "
        "res_partner.vat (%s skipped)",
        salvaged,
        column,
        skipped,
    )


def _salvage_rg(env):
    if not openupgrade.column_exists(env.cr, "hr_employee", "rg"):
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE res_partner p
           SET l10n_br_rg_code = btrim(e.rg),
               write_uid = %(uid)s,
               write_date = NOW() AT TIME ZONE 'UTC'
          FROM hr_employee e
         WHERE e.work_contact_id = p.id
           AND btrim(coalesce(e.rg, '')) != ''
           AND coalesce(p.l10n_br_rg_code, '') = ''
        """,
        {"uid": env.uid},
    )


@openupgrade.migrate()
def migrate(env, version):
    """Salvage the legacy hr_employee.cnpj_cpf ghost column and drop it.

    The column was introduced in 2022 but never displayed in any view nor
    read by any business logic. Any residual value is copied to the
    employee work contact (res.partner) vat, stored unformatted following
    the l10n_br_base convention, only when the partner has no vat yet, the
    value is a valid CNPJ/CPF and it is not already used by another
    partner (mirroring the res.partner _check_vat constraint that raw SQL
    bypasses). cnpj_cpf_stripped is synced as it is a stored computed
    field.

    Databases coming from 12.0 also keep the cpf and rg columns, which were
    related to the home address and now live on the work contact (vat and
    l10n_br_rg_code). They are carried the same way and kept, since a value
    that is not a valid CPF cannot be salvaged.
    """
    _salvage_vat(env, "cnpj_cpf")
    openupgrade.drop_columns(env.cr, [("hr_employee", "cnpj_cpf")])
    _salvage_vat(env, "cpf")
    _salvage_rg(env)
