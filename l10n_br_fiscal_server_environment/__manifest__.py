# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Brazilian Fiscal Environment via server_environment",
    "summary": "NF-e and NFS-e environment (production/homologation) of the "
    "company set by the server environment file",
    "category": "Localisation",
    "license": "AGPL-3",
    "author": "KMEE, Odoo Community Association (OCA)",
    "maintainers": ["mileo"],
    "website": "https://github.com/OCA/l10n-brazil",
    "development_status": "Beta",
    "version": "18.0.1.0.0",
    "depends": [
        "l10n_br_nfe",
        "l10n_br_nfse",
        "server_environment",
    ],
    "demo": ["demo/res_company_demo.xml"],
    "uninstall_hook": "uninstall_hook",
}
