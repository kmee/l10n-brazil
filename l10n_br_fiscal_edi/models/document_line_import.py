# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models

from odoo.addons.l10n_br_fiscal.constants.fiscal import FISCAL_IN, FISCAL_OUT


class DocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    def _find_or_create_supplierinfo(self):
        """The partner of a document the company issued is a customer: what the
        review of its lines teaches is not a mapping of a supplier."""
        received = self.filtered(
            lambda line: line.document_id.fiscal_operation_type != FISCAL_OUT
        )
        return super(DocumentLine, received)._find_or_create_supplierinfo()

    def _edi_import_barcode(self):
        """Extension point: the valid barcode (GTIN) the file declares for the
        product of the line, when the reader knows one."""
        self.ensure_one()
        return False

    def _edi_import_product_vals(self):
        """Values of the product to create from the line of an imported document.
        The base takes what the line declares with certainty: the description, the
        unit, the NCM, the CEST and the origin, and the barcode when the reader
        declares one. The category is the one of the company, when it has one; no
        account and no price.

        In a document the company issued the code of the file is the internal code
        of the product. In a document received it is the code of the supplier: it
        goes to the supplier info (the de-para) and never becomes the internal code,
        and the product is born purchasable and not sellable."""
        self.ensure_one()
        document = self.document_id
        if document.fiscal_operation_type == FISCAL_IN:
            vals = {
                "name": self._get_partner_product_name() or self.name,
                "purchase_ok": True,
                "sale_ok": False,
                # no price of sale is invented: the Odoo default is 1.00
                "list_price": 0.0,
            }
        else:
            vals = {
                "name": self.name,
                "default_code": self._get_partner_product_code(),
            }
        if self.uom_id:
            vals.update(uom_id=self.uom_id.id, uom_po_id=self.uom_id.id)
        if self.ncm_id:
            vals["ncm_id"] = self.ncm_id.id
        if self.cest_id:
            vals["cest_id"] = self.cest_id.id
        if self.icms_origin:
            vals["icms_origin"] = self.icms_origin
        barcode = self._edi_import_barcode()
        if barcode:
            vals["barcode"] = barcode
        categ = document.company_id.import_product_categ_id
        if categ:
            vals["categ_id"] = categ.id
        return vals
