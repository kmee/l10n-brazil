# Copyright 2026 KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
{
    "name": "CNAB Structure - HR bridge",
    "summary": """
        Detects employees (hr.employee) as salary payees in the CNAB payment
        rules, without making hr a dependency of the CNAB modules.""",
    "version": "18.0.1.0.0",
    "author": "KMEE, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "license": "AGPL-3",
    "depends": [
        "l10n_br_cnab_structure",
        "hr",
    ],
    "auto_install": True,
    "installable": True,
}
