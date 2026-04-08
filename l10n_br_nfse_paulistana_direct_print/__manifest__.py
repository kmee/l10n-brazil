{
    "name": "Direct print of Paulistana NFS-e",
    "summary": """
        This module extends the l10n_br_nfse_paulistana module by adding
        the functionality to print the Electronic Service Invoice (NFS-e)
        directly from the São Paulo municipality's website.
    """,
    "version": "18.0.1.0.0",
    "author": "Engenere, Escodoo, Odoo Community Association (OCA)",
    "category": "Localization",
    "license": "AGPL-3",
    "website": "https://www.engenere.one",
    "depends": [
        "l10n_br_nfse_paulistana",
        "l10n_br_account",
    ],
    "data": [
        "views/document_view.xml",
    ],
    "installable": True,
    "auto_install": False,
}
