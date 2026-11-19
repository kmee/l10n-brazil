# Copyright (C) 2021  Gabriel Cardoso de Faria - Kmee
# Copyright (C) 2022  Renan Hiroki Bastos - Kmee
# Copyright (C) 2023  Luiz Felipe do Divino - Kmee
# Copyright (C) 2023  Felipe Zago Rodrigues - Kmee
# Copyright (C) 2026  Raphaël Valyi - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from collections import Counter

from erpbrasil.base.fiscal.cnpj_cpf import formata

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression

from odoo.addons.l10n_br_fiscal.constants.fiscal import MODELO_FISCAL_NFE

# cStat of the authorization protocol: cancellation (101, 151, 155) and
# denied use (110, 301, 302, 303)
NFE_CANCELLED_STATUS = ("101", "151", "155")
NFE_DENIED_STATUS = ("110", "301", "302", "303")


class DocumentImportWizard(models.TransientModel):
    _inherit = "l10n_br_fiscal.document.import.wizard"

    nat_op = fields.Char(string="Natureza da Operação")

    @api.model
    def _detect_binding(self, binding):
        """
        Register the import_xml NFe importer
        """
        if hasattr(binding, "infNFe") or hasattr(binding, "NFe"):
            return self._detect_document_type(MODELO_FISCAL_NFE)
        return super()._detect_binding(binding)

    def _extract_binding_data(self, binding):
        if hasattr(binding, "NFe"):
            binding = binding.NFe
        res = super()._extract_binding_data(binding)
        if self.document_type == MODELO_FISCAL_NFE:
            self._extract_key_information(binding.infNFe.Id[3:])
            infNFe = binding.infNFe
            self.nat_op = infNFe.ide.natOp
            self.amount_total = infNFe.total.ICMSTot.vNF
            self.fiscal_operation_id = self._nfe_default_operation(infNFe)
            self._create_imported_products_by_xml(binding)
        return res

    def _nfe_default_operation(self, infNFe):
        """Use the company operation for a received NF-e.

        An empty company operation, and an NF-e issued by this company,
        keep the match by the most common CFOP.
        """
        self.ensure_one()
        operation = self.company_id.nfe_import_fiscal_operation_id
        if operation and self.fiscal_operation_type == "in":
            return operation
        return self._find_fiscal_operation(
            self._most_common_cfop(infNFe),
            self.nat_op,
            self.fiscal_operation_type,
        )

    def _import_block_reason(self):
        reason = super()._import_block_reason()
        if reason or self.document_type != MODELO_FISCAL_NFE or not self.file:
            return reason
        # the authorization protocol travelling with the file tells whether
        # the note was cancelled or denied at the source
        protocol = getattr(self._parse_file_data(self.file), "protNFe", None)
        status = str(getattr(getattr(protocol, "infProt", None), "cStat", "") or "")
        if status in NFE_CANCELLED_STATUS:
            return _("This NF-e was cancelled at the source and cannot be imported.")
        if status in NFE_DENIED_STATUS:
            return _("This NF-e was denied at the source and cannot be imported.")
        return reason

    @api.model
    def _most_common_cfop(self, infNFe):
        """Return the CFOP shared by most of the NFe lines.

        A single NFe can mix CFOPs (e.g. a freight or one-off line), so
        picking the first line's CFOP is unreliable. The majority CFOP
        better represents the document's fiscal operation.
        """
        cfops = [det.prod.CFOP for det in infNFe.det if det.prod.CFOP]
        if not cfops:
            return False
        return Counter(cfops).most_common(1)[0][0]

    def _destination_partner_from_binding(self, binding):
        if self.document_type == MODELO_FISCAL_NFE:
            if hasattr(binding, "NFe"):
                binding = binding.NFe
            dest = binding.infNFe.dest
            # the destination can be an individual, identified by CPF
            dest_cnpj_cpf = dest.CNPJ or dest.CPF
            self.destination_partner_id = self._search_partner(
                cnpj=dest_cnpj_cpf,
                legal_name=dest.xNome,
            )
            self.issuer_legal_name = binding.infNFe.emit.xNome
            self.issuer_name = binding.infNFe.emit.xFant

            self.destination_cnpj = formata(dest_cnpj_cpf) if dest_cnpj_cpf else False
            self.destination_name = dest.xNome

    def _parse_file(self):
        binding = super()._parse_file()
        if hasattr(binding, "NFe"):
            binding = binding.NFe
        return binding

    def _check_xml_data(self, binding):
        document = self._document_key_from_binding(binding)
        nfe_model_code = self.env.ref("l10n_br_fiscal.document_55").code

        if document.modelo_documento != nfe_model_code:
            raise UserError(
                _(f"Incorrect fiscal document model! Accepted one is {nfe_model_code}")
            )

    def _create_imported_products_by_xml(self, binding):
        product_ids = []
        for product in binding.infNFe.det:
            product_ids.append(
                self.env["l10n_br_fiscal.document.import.wizard.line"]
                .create(self._prepare_imported_product_values(product))
                .id
            )

        self.imported_products_ids = [Command.set(product_ids)]

    def _prepare_imported_product_values(self, product):
        taxes = self._get_taxes_from_xml_product(product)
        supplier_id = self._search_product_supplier_by_product_code(product.prod.cProd)
        product_id, product_source = self._match_product_with_source(product.prod)
        uom_id = self._match_uom_by_code(product.prod.uCom, product.prod.uTrib)
        match_source = self._match_import_candidate(product.prod, product_id)
        # the order the supplier declared (xPed and nItemPed) and the candidate
        # that pins its line: nothing was guessed
        declared_line = self._match_po_line(product.prod)
        declared = bool(
            match_source and declared_line and match_source.id == declared_line.id
        )
        if match_source:
            # the source reference is more authoritative than the generic
            # product/UoM match: it pins the exact PO/picking line.
            product_id = match_source.product_id
            uom_id = match_source.uom_id
            if declared:
                product_source = "order"

        return {
            "product_name": product.prod.xProd,
            "product_code": product.prod.cProd,
            "ncm_xml": product.prod.NCM,
            "cfop_xml": product.prod.CFOP,
            "product_id": product_id and product_id.id or False,
            "match_source_id": match_source.id or False,
            "match_source_trusted": declared,
            "product_source": product_id and product_source or False,
            "icms_percent": taxes["pICMS"],
            "icms_value": taxes["vICMS"],
            "ipi_percent": taxes["pIPI"],
            "ipi_value": taxes["vIPI"],
            "uom_internal": uom_id.id,
            "uom_com": product.prod.uCom,
            "quantity_com": product.prod.qCom,
            "price_unit_com": product.prod.vUnCom,
            "uom_trib": product.prod.uTrib,
            "quantity_trib": product.prod.qTrib,
            "price_unit_trib": product.prod.vUnTrib,
            "total": product.prod.vProd,
            "import_xml_id": self._origin.id or self.id,
            "product_supplier_id": supplier_id.id,
            "uom_conversion_factor": supplier_id.partner_uom_factor or 1,
        }

    def _search_product_supplier_by_product_code(self, code):
        return self.env["product.supplierinfo"].search(
            [
                # the preview runs before the document, and so before the
                # partner, exist: only the issuer is known then
                ("partner_id", "=", (self.partner_id or self.issuer_partner_id).id),
                ("product_code", "=", code),
            ],
            limit=1,
        )

    def _get_product_by_supplier(self, code):
        supplier_id = self._search_product_supplier_by_product_code(code)
        if not supplier_id:
            return False

        if supplier_id.product_id:
            return supplier_id.product_id

        variant_ids = supplier_id.product_tmpl_id.product_variant_ids
        return variant_ids[0]

    def _match_product(self, xml_product):
        return self._match_product_with_source(xml_product)[0]

    def _match_product_with_source(self, xml_product):
        """The internal product of an XML line, and where it came from.

        ``order``: the line of the purchase order the supplier declared;
        ``supplier``: the de-para already learned for this same supplier;
        ``guess``: found by internal reference, barcode, which anyone may share
        with another product, so it is only a suggestion for a person to
        confirm. Nothing matched: ``(empty, False)``.
        """
        product_id = self._match_product_by_purchase(xml_product)
        if product_id:
            return product_id, "order"

        product_id = self._get_product_by_supplier(xml_product.cProd)
        if product_id:
            return product_id, "supplier"

        domain = []
        if hasattr(xml_product, "cProd") and xml_product.cProd:
            domain = expression.OR([domain, [("default_code", "=", xml_product.cProd)]])

        if hasattr(xml_product, "cEANTrib") and xml_product.cEANTrib != "SEM GTIN":
            domain = expression.OR([domain, [("barcode", "=", xml_product.cEANTrib)]])

        rec_id = False
        if domain:
            rec_id = self.env["product.product"].search(domain, limit=1)
        return rec_id, "guess" if rec_id else False

    def _match_product_by_purchase(self, xml_product):
        """Priority match from the referenced purchase order.

        Thin wrapper over the generic ``_match_po_line`` (l10n_br_fiscal_edi)
        returning only the product, kept for backward compatibility.
        """
        po_line = self._match_po_line(xml_product)
        return po_line.product_id if po_line else False

    def _get_taxes_from_xml_product(self, product):
        vICMS = 0
        pICMS = 0
        pIPI = 0
        vIPI = 0
        icms_tags = [tag for tag in dir(product.imposto.ICMS) if tag.startswith("ICMS")]
        for tag in icms_tags:
            if getattr(product.imposto.ICMS, tag) is not None:
                icms_choice = getattr(product.imposto.ICMS, tag)
        if hasattr(icms_choice, "pICMS"):
            pICMS = icms_choice.pICMS
        if hasattr(icms_choice, "vICMS"):
            vICMS = icms_choice.vICMS
        if hasattr(product.imposto.IPI, "IPITrib"):
            ipi_trib = product.imposto.IPI.IPITrib
            if hasattr(ipi_trib, "pIPI"):
                pIPI = ipi_trib.pIPI
            if hasattr(ipi_trib, "vIPI"):
                vIPI = ipi_trib.vIPI

        return {"vICMS": vICMS, "pICMS": pICMS, "vIPI": vIPI, "pIPI": pIPI}

    def _create_edoc_from_file(self):
        if self.document_type == MODELO_FISCAL_NFE:
            # The document is materialized FAITHFULLY from the file (the
            # binding is never rewritten); the de-para reviewed in the
            # wizard grid is then applied on the persisted lines, which is
            # the single write path (_apply_import_depara).
            binding = self._parse_file()
            edoc = self.env["l10n_br_fiscal.document"].import_binding_nfe(
                binding,
                edoc_type=self.fiscal_operation_type,
                # the box decides: unchecked, no product is created and the
                # line of an unmapped product stays pending for a person
                create_missing_products=self.allow_product_creation,
            )
            edoc.document_type_id = self.env.ref("l10n_br_fiscal.document_55").id
            edoc.fiscal_operation_id = self.fiscal_operation_id

            if not self.partner_id:
                self.partner_id = edoc.partner_id

            self._attach_original_nfe_xml_to_document(edoc)
            edoc._init_import_states()
            self._apply_wizard_depara(edoc)
            # the taxes read from the file fill the tax fields of the lines,
            # but not the fiscal taxes column
            edoc.fiscal_line_ids._update_fiscal_tax_ids()

            if self.fiscal_operation_type == "in":
                self._update_new_products_standard_price(edoc)

            return binding, edoc
        return super()._create_edoc_from_file()

    def _attach_original_nfe_xml_to_document(self, edoc):
        """Attach the untouched supplier XML and link it as the document
        original XML (used by View XML / View PDF on imported documents)."""
        attachment = edoc._attach_imported_xml(
            self.file, f"NFe-Importada-{edoc.document_key}.xml"
        )
        edoc.original_xml_file_id = attachment
        return attachment

    def _update_new_products_standard_price(self, edoc):
        """Produtos CRIADOS neste import: o custo padrão deve ser o custo de
        aquisição LÍQUIDO da linha (Art. 301 RIR/2018, CPC 16), não o vUnCom
        bruto da NF (que embute ICMS/PIS/COFINS recuperáveis e exclui ICMS-ST/
        IPI/frete). Produtos pré-existentes não são tocados (o custo deles é
        gerido pela valorização de estoque).

        Produto criado neste import = create_date na mesma transação do
        documento (now() do PostgreSQL é fixo por transação)."""
        for line in edoc.fiscal_line_ids.filtered("product_id"):
            product = line.product_id
            if (
                self._product_created_by_import(product, edoc)
                and line.stock_cost_unit
                and product.standard_price != line.stock_cost_unit
            ):
                product.standard_price = line.stock_cost_unit

    @api.model
    def _product_created_by_import(self, product, edoc):
        """True for a product created by the import of this document (created
        in the transaction of the document), not found among the existing."""
        return bool(
            product and edoc.create_date and product.create_date >= edoc.create_date
        )

    def _apply_wizard_depara(self, edoc):
        """Apply the de-para reviewed in the wizard grid on the persisted
        document lines (both follow the file line order)."""
        # both recordsets follow the file line order, one wizard line per det;
        # the origin of the lines is suggested once, for the whole document,
        # after the de-para (not once per line)
        for wizard_line, line in zip(
            self.imported_products_ids, edoc.fiscal_line_ids, strict=True
        ):
            line = line.with_context(import_origin_deferred=True)
            if wizard_line.product_id:
                line._apply_import_depara(
                    product=wizard_line.product_id,
                    # the legacy flow used the taxation unit as the internal
                    # unit when no de-para was reviewed
                    uom=wizard_line.uom_internal or line.uot_id,
                    factor=wizard_line.uom_conversion_factor,
                    fiscal_operation=self.fiscal_operation_id,
                    # a product only guessed by the import stays a suggestion
                    # (and teaches nothing) until a person confirms it
                    confirm=wizard_line._product_decided(),
                )
            else:
                if self.fiscal_operation_id:
                    # operation de-para only: the line keeps waiting for the
                    # product review.
                    line.fiscal_operation_id = self.fiscal_operation_id
                if line.product_id and not line.uom_id and wizard_line.uom_internal:
                    # Product created during this import (allow_product_creation):
                    # its uom was not resolved from the XML at line-creation time
                    # (the line compute ran before the product's units were set),
                    # so fall back to the unit the wizard matched from uCom/uTrib
                    # and align the created product's units with it.
                    line.uom_id = wizard_line.uom_internal
                    line.product_id.uom_id = wizard_line.uom_internal
                    line.product_id.uom_po_id = wizard_line.uom_internal
                if self._product_created_by_import(line.product_id, edoc):
                    # the person asked for the unmapped products to be created
                    # from the file: the product is the line of the file, there
                    # is no guess left to review
                    line._apply_import_depara(
                        product=line.product_id,
                        uom=line.uom_id,
                        factor=1.0,
                        fiscal_operation=self.fiscal_operation_id,
                    )
            if wizard_line.new_cfop_id:
                # explicit CFOP override reviewed by the user, applied after
                # the operation remap.
                line.cfop_id = wizard_line.new_cfop_id
        edoc.fiscal_line_ids._suggest_import_origin()


class DocumentImportWizardLine(models.TransientModel):
    """NFe specialization of the generic fiscal import wizard line.

    It only adds the NFe specific data: the commercial/tax unit split and
    the ICMS/IPI taxes read from the XML. The supplier info learning now
    happens on the persisted document line (_apply_import_depara).
    """

    _inherit = "l10n_br_fiscal.document.import.wizard.line"

    product_source = fields.Selection(
        selection=[
            ("order", "Purchase order declared by the supplier"),
            ("supplier", "De-para of the supplier"),
            ("guess", "Guessed by the import"),
            ("user", "Chosen in the grid"),
        ],
        copy=False,
        help="Technical: where the internal product of the line came from. Only "
        "the product that comes from the order the supplier declared, from the "
        "de-para already learned for this supplier, or from a person is "
        "resolved by the import; a guess (internal reference, barcode) stays a "
        "suggestion until it is confirmed.",
    )

    product_confirmed = fields.Boolean(
        string="Confirmed",
        copy=False,
        help="Check it to confirm the suggested product of the line: the line is "
        "then resolved and the supplier de-para is learned. Choosing another "
        "product in the grid confirms it as well.",
    )

    uom_trib = fields.Char(string="UOM Fiscal")

    quantity_trib = fields.Float()

    price_unit_trib = fields.Float(string="Fiscal Price Unit")

    icms_percent = fields.Char(string="Alíquota ICMS")

    icms_value = fields.Char(string="ICMS Value")

    ipi_percent = fields.Char(string="Alíquota IPI")

    ipi_value = fields.Char(string="IPI Value")

    def write(self, vals):
        if "product_id" in vals and "product_source" not in vals:
            # the product was chosen (or cleared) in the grid: a human decision
            vals = dict(vals, product_source="user" if vals["product_id"] else False)
        return super().write(vals)

    def _product_decided(self):
        """True when the product of the line needs no review: it came from the
        order the supplier declared, from the de-para of this supplier, or a
        person chose or confirmed it."""
        self.ensure_one()
        return bool(
            self.product_confirmed
            or self.product_source in ("order", "supplier", "user")
        )
