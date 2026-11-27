# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo.tools.convert import convert_file

_logger = logging.getLogger(__name__)

# Order matters: the second file reuses the supplier of the first.
DEMO_FILES = (
    "demo/purchase_edi_demo.xml",
    "demo/purchase_stock_edi_demo.xml",
)


def post_init_hook(env):
    """Load the demo of the import of purchases, which is made of sample NF-e files.

    The links of the purchases do not depend on the type of the document that was
    imported, so the demo is not in the ``demo`` key of the manifest: that would
    break the installation with demo data in a database with no NF-e. Here it is
    loaded only when the demo data was asked for and the NF-e module is already
    installed, which has the reader of the sample files.
    """
    modules = env["ir.module.module"].sudo()
    this = modules.search([("name", "=", "l10n_br_purchase_stock_edi")])
    nfe = modules.search_count(
        [("name", "=", "l10n_br_nfe"), ("state", "in", ("installed", "to upgrade"))]
    )
    if not (this.demo and nfe):
        return
    for filename in DEMO_FILES:
        _logger.info("Loading the demo file %s", filename)
        convert_file(
            env,
            "l10n_br_purchase_stock_edi",
            filename,
            {},
            mode="init",
            noupdate=True,
            kind="demo",
        )
