# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64

from odoo import _, api, fields, models

SOURCE_FORMAT = [
    ("xml", "Siscomex XML"),
    ("txt", "NF-e TXT Layout"),
]

DECLARATION_TYPE = [
    ("di", "Declaração de Importação"),
    ("duimp", "Declaração Única de Importação"),
]

ADJUSTMENT_KIND = [
    ("acrescimo", "Acréscimo"),
    ("deducao", "Dedução"),
]


class ImportDeclaration(models.Model):
    _name = "l10n_br_fiscal.import.declaration"
    _description = "Import Declaration (DI/DUIMP)"
    _order = "registration_date desc, number"

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )

    number = fields.Char(string="DI/DUIMP Number")
    declaration_type = fields.Selection(
        selection=DECLARATION_TYPE, default="di", required=True
    )
    rectification_number = fields.Char(string="Rectification Number")

    registration_date = fields.Date(string="Registration Date")
    clearance_date = fields.Date(string="Clearance Date")

    clearance_place = fields.Char(string="Clearance Place")
    clearance_state_id = fields.Many2one(
        comodel_name="res.country.state",
        domain="[('country_id.code', '=', 'BR')]",
        string="Clearance State",
    )
    urf_clearance_code = fields.Char(string="Dispatch URF Code")
    urf_clearance_name = fields.Char(string="Dispatch URF Name")
    urf_entry_code = fields.Char(string="Entry URF Code")
    urf_entry_name = fields.Char(string="Entry URF Name")

    transport_via = fields.Char(string="Transport Via Code")
    intermediation_code = fields.Char(string="Intermediation Code")
    operation_type_code = fields.Char(string="Operation Type Code")

    importer_document = fields.Char(string="Importer Document")
    importer_partner_id = fields.Many2one(
        comodel_name="res.partner", string="Importer"
    )
    acquirer_partner_id = fields.Many2one(
        comodel_name="res.partner", string="Third-Party Acquirer"
    )
    exporter_code = fields.Char(string="Exporter Code")
    exporter_name = fields.Char(string="Exporter Name")
    origin_country_id = fields.Many2one(
        comodel_name="res.country", string="Origin Country"
    )
    acquisition_country_id = fields.Many2one(
        comodel_name="res.country", string="Acquisition Country"
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency", string="Foreign Currency"
    )
    amount_foreign = fields.Monetary(
        string="Total in Foreign Currency", currency_field="currency_id"
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", string="Company Currency"
    )
    customs_value = fields.Monetary(
        string="Total Customs Value", currency_field="company_currency_id"
    )
    exchange_rate = fields.Float(
        string="Exchange Rate", digits="Product Price", help="""
        The rate the declaration implies, amount in company currency divided
        by amount in foreign currency, not a rate read from Odoo. This is
        the taxa de câmbio do registro, a legal fact stated by the DI.
        """
    )
    exchange_rate_stated = fields.Boolean(string="Exchange Rate Stated")

    freight_value = fields.Monetary(
        string="Total Freight", currency_field="company_currency_id"
    )
    freight_stated = fields.Boolean(string="Freight Stated")
    insurance_value = fields.Monetary(
        string="Total Insurance", currency_field="company_currency_id"
    )
    insurance_stated = fields.Boolean(string="Insurance Stated")
    afrmm_value = fields.Monetary(
        string="AFRMM", currency_field="company_currency_id"
    )
    afrmm_stated = fields.Boolean(string="AFRMM Stated")
    customhouse_charges = fields.Monetary(
        string="Siscomex Fee / Customhouse Charges",
        currency_field="company_currency_id",
    )
    customhouse_charges_stated = fields.Boolean(string="Customhouse Charges Stated")
    penalty_value = fields.Monetary(
        string="Penalty (Multa)", currency_field="company_currency_id"
    )
    interest_value = fields.Monetary(
        string="Interest (Juros e Encargos)", currency_field="company_currency_id"
    )
    icms_value = fields.Monetary(
        string="ICMS", currency_field="company_currency_id"
    )

    gross_weight = fields.Float(string="Gross Weight")
    net_weight = fields.Float(string="Net Weight")

    source_format = fields.Selection(selection=SOURCE_FORMAT, required=True)
    raw_file = fields.Binary(string="Source File", attachment=True)
    raw_filename = fields.Char(string="Source Filename")
    parser_version = fields.Char(string="Parser Version")
    stated_field_names = fields.Text(
        string="Stated Fields",
        help="Comma separated list of fields the source actually stated.",
    )

    addition_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.import.declaration.addition",
        inverse_name="declaration_id",
        string="Additions",
    )
    payment_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.import.declaration.payment",
        inverse_name="declaration_id",
        string="Payments",
    )
    document_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.import.declaration.document",
        inverse_name="declaration_id",
        string="Dispatch Documents",
    )
    extra_field_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.import.declaration.field",
        inverse_name="declaration_id",
        domain=[("addition_id", "=", False)],
        string="Unmapped Header Fields",
    )
    divergence_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.import.declaration.divergence",
        inverse_name="declaration_id",
        string="Divergences",
    )

    # Tax domain, (declared base, declared rate, declared value) field names
    # on the addition, (computed base, computed rate, computed value) field
    # names on the fiscal line — the addition names its rate `*_rate` and the
    # line names the same figure `*_percent`, so the two need to be told
    # apart. The base is the same valor aduaneiro for II, PIS and COFINS
    # (Art. 75, Decreto 6.759/09; Art. 7º, I, Lei 10.865/04), and IPI's own
    # base (Art. 190, I, "a", Decreto 7.212/10) only exists on an addition
    # the TXT reader stated it for.
    _RECONCILE_TAXES = (
        ("ii", ("ii_base", "ii_rate", "ii_value"), ("ii_base", "ii_percent", "ii_value")),
        (
            "ipi",
            ("ipi_base", "ipi_rate", "ipi_value"),
            ("ipi_base", "ipi_percent", "ipi_value"),
        ),
        (
            "pis",
            ("ii_base", "pis_rate", "pis_value"),
            ("pis_base", "pis_percent", "pis_value"),
        ),
        (
            "cofins",
            ("ii_base", "cofins_rate", "cofins_value"),
            ("cofins_base", "cofins_percent", "cofins_value"),
        ),
    )

    def _reconcile(self):
        """Compare what the declaration charged against what the engine
        computed for the lines each addition claims, and record every
        divergence found — this method never blocks; a value divergence
        that should stop the note is for whoever calls it to act on.

        Compares base, rate and value for II, IPI, PIS and COFINS, one
        addition at a time, against the sum (value) or the common figure
        (base, rate) of the fiscal lines the wizard tied to it. An addition
        with no line tied to it yet has nothing to compare against and is
        skipped, not flagged.
        """
        self.ensure_one()
        self.divergence_ids.unlink()
        currency = self.company_currency_id
        rows = []
        for addition in self.addition_ids:
            lines = addition.fiscal_line_ids
            if not lines:
                continue
            tolerance = (currency.rounding or 0.01) * len(lines)
            for tax_domain, declared_fields, computed_fields in self._RECONCILE_TAXES:
                declared_base_f, declared_rate_f, declared_value_f = declared_fields
                computed_base_f, computed_rate_f, computed_value_f = computed_fields

                declared_value = addition[declared_value_f]
                computed_value = sum(lines.mapped(computed_value_f))
                rows.append(
                    self._divergence_row(
                        addition,
                        lines,
                        tax_domain,
                        "value",
                        declared_value,
                        computed_value,
                        tolerance,
                    )
                )

                declared_base = addition[declared_base_f]
                if declared_base:
                    computed_bases = set(
                        currency.round(value)
                        for value in lines.mapped(computed_base_f)
                    )
                    computed_base = (
                        computed_bases.pop()
                        if len(computed_bases) == 1
                        else sum(lines.mapped(computed_base_f))
                    )
                    rows.append(
                        self._divergence_row(
                            addition,
                            lines,
                            tax_domain,
                            "base",
                            declared_base,
                            computed_base,
                            tolerance,
                        )
                    )

                declared_rate = addition[declared_rate_f]
                if declared_rate:
                    computed_rates = set(
                        round(value, 2) for value in lines.mapped(computed_rate_f)
                    )
                    computed_rate = (
                        computed_rates.pop()
                        if len(computed_rates) == 1
                        else lines[:1][computed_rate_f]
                    )
                    rows.append(
                        self._divergence_row(
                            addition,
                            lines,
                            tax_domain,
                            "percent",
                            declared_rate,
                            computed_rate,
                            0.01,
                        )
                    )
        rows = [row for row in rows if row]
        if rows:
            self.env["l10n_br_fiscal.import.declaration.divergence"].create(rows)
        return self.divergence_ids

    def _divergence_row(
        self, addition, lines, tax_domain, dimension, declared, computed, tolerance
    ):
        difference = computed - declared
        if abs(difference) <= tolerance:
            return None
        severity = "rounding" if abs(difference) <= tolerance * 3 else "divergence"
        explanation = {
            "value": _(
                "The declaration charged %(declared)s of %(tax)s and the "
                "lines close at %(computed)s."
            ),
            "base": _(
                "The declaration's base for %(tax)s is %(declared)s and the "
                "lines compute %(computed)s — check the tax configuration if "
                "the value still closes."
            ),
            "percent": _(
                "The declaration charged %(tax)s at %(declared)s%% and the "
                "lines carry %(computed)s%% — a configuration mismatch, not "
                "a value to force."
            ),
        }[dimension] % {
            "tax": tax_domain.upper(),
            "declared": declared,
            "computed": computed,
        }
        return {
            "declaration_id": self.id,
            "addition_id": addition.id,
            "fiscal_line_id": lines[:1].id,
            "tax_domain": tax_domain,
            "dimension": dimension,
            "declared": declared,
            "computed": computed,
            "difference": difference,
            "severity": severity,
            "explanation": explanation,
        }

    @api.model
    def create_from_parsed(
        self, declaration, source_format, raw_file=None, raw_filename=None
    ):
        """Persist what `declaration_xml.parse_*` read, nothing discarded.

        `declaration` is the plain dict either parser returns. Every key it
        already produces lands on a typed column here; every tag the parser
        could not name (`unmapped_tags`) lands on `extra_field_ids` instead of
        vanishing, so a file that carries something this reader has no slot
        for is still fully on record, not silently short of it.
        """
        state = self.env["res.country.state"].search(
            [
                ("code", "=", declaration.get("clearance_state")),
                ("country_id.code", "=", "BR"),
            ],
            limit=1,
        )
        values = {
            "company_id": self.env.company.id,
            "number": declaration.get("number") or "",
            "registration_date": declaration.get("registration_date") or False,
            "clearance_date": declaration.get("clearance_date") or False,
            "clearance_place": declaration.get("clearance_place") or "",
            "clearance_state_id": state.id,
            "transport_via": declaration.get("transport_via") or "",
            "operation_type_code": declaration.get("operation_type_code") or "",
            "intermediation_code": declaration.get("intermediation_code") or "",
            "importer_document": declaration.get("importer_document") or "",
            "exporter_code": declaration.get("exporter_code") or "",
            "freight_value": declaration.get("freight") or 0.0,
            "freight_stated": bool(declaration.get("freight")),
            "insurance_value": declaration.get("insurance") or 0.0,
            "insurance_stated": bool(declaration.get("insurance")),
            "afrmm_value": declaration.get("afrmm") or 0.0,
            "afrmm_stated": bool(declaration.get("afrmm")),
            "customhouse_charges": declaration.get("customhouse_charges") or 0.0,
            "customhouse_charges_stated": bool(
                declaration.get("customhouse_charges")
            ),
            "icms_value": declaration.get("icms_value") or 0.0,
            "gross_weight": declaration.get("gross_weight") or 0.0,
            "net_weight": declaration.get("net_weight") or 0.0,
            "source_format": source_format,
            "raw_filename": raw_filename or False,
            "stated_field_names": ", ".join(
                sorted(
                    key
                    for key, value in declaration.items()
                    if key not in ("additions", "unmapped_tags", "regime_signals")
                    and value
                )
            )
            or False,
            "extra_field_ids": [
                (0, 0, {"record": "header", "tag": tag, "raw_value": ""})
                for tag in declaration.get("unmapped_tags", [])
            ],
            "addition_ids": [
                (0, 0, self._addition_values_from_parsed(addition))
                for addition in declaration.get("additions", [])
            ],
        }
        if raw_file is not None:
            values["raw_file"] = (
                base64.b64encode(raw_file)
                if isinstance(raw_file, bytes)
                else raw_file
            )
        return self.create(values)

    @api.model
    def _addition_values_from_parsed(self, addition):
        ncm = self.env["l10n_br_fiscal.ncm"].search(
            [("code", "=", addition.get("ncm"))], limit=1
        )
        return {
            "number": addition.get("number") or "",
            "ncm_id": ncm.id,
            "amount_brl": addition.get("goods_value") or 0.0,
            "net_weight": addition.get("net_weight") or 0.0,
            "incoterm": addition.get("incoterm") or "",
            "exporter_name": addition.get("exporter") or "",
            "manufacturer_name": addition.get("manufacturer") or "",
            "drawback_act": addition.get("drawback_act") or "",
            "ii_base": addition.get("customs_value") or 0.0,
            "ii_rate": addition.get("ii_rate") or 0.0,
            "ii_value": addition.get("ii_value") or 0.0,
            "ii_regime_code": addition.get("ii_regime_code") or "",
            "ipi_base": addition.get("ipi_base") or 0.0,
            "ipi_rate": addition.get("ipi_rate") or 0.0,
            "ipi_value": addition.get("ipi_value") or 0.0,
            "ipi_regime_code": addition.get("ipi_regime_code") or "",
            "pis_rate": addition.get("pis_rate") or 0.0,
            "pis_value": addition.get("pis_value") or 0.0,
            "cofins_rate": addition.get("cofins_rate") or 0.0,
            "cofins_value": addition.get("cofins_value") or 0.0,
            "pis_cofins_regime_code": addition.get("pis_cofins_regime_code") or "",
            "line_ids": [
                (
                    0,
                    0,
                    {
                        "sequence": int(item.get("sequence") or 0) or 10,
                        "description": item.get("description") or "",
                        "quantity": item.get("quantity") or 0.0,
                        "unit_value": item.get("unit_value") or 0.0,
                        "uom_name": item.get("uom") or "",
                    },
                )
                for item in addition.get("items", [])
            ],
        }


class ImportDeclarationAddition(models.Model):
    _name = "l10n_br_fiscal.import.declaration.addition"
    _description = "Import Declaration Addition (Adição)"
    _order = "sequence, number"

    declaration_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.import.declaration",
        required=True,
        ondelete="cascade",
    )
    company_currency_id = fields.Many2one(
        related="declaration_id.company_currency_id"
    )
    sequence = fields.Integer(default=10)
    number = fields.Char(string="Addition Number")

    ncm_id = fields.Many2one(comodel_name="l10n_br_fiscal.ncm", string="NCM")
    naladi_sh_code = fields.Char(string="NALADI/SH Code")
    naladi_ncca_code = fields.Char(string="NALADI/NCCA Code")
    destaque_ncm = fields.Char(string="NCM Highlight (Destaque)")

    incoterm = fields.Char(string="Incoterm")
    exporter_code = fields.Char(string="Exporter Code")
    exporter_name = fields.Char(string="Exporter Name")
    manufacturer_code = fields.Char(string="Manufacturer Code")
    manufacturer_name = fields.Char(string="Manufacturer Name")
    origin_country_id = fields.Many2one(
        comodel_name="res.country", string="Origin Country"
    )
    acquisition_country_id = fields.Many2one(
        comodel_name="res.country", string="Acquisition Country"
    )

    currency_id = fields.Many2one(comodel_name="res.currency", string="Currency")
    amount_foreign = fields.Monetary(
        string="Amount (Foreign Currency)", currency_field="currency_id"
    )
    amount_brl = fields.Monetary(
        string="Amount (BRL)", currency_field="company_currency_id"
    )
    freight_value = fields.Monetary(
        string="Freight", currency_field="company_currency_id"
    )
    insurance_value = fields.Monetary(
        string="Insurance", currency_field="company_currency_id"
    )
    net_weight = fields.Float(string="Net Weight")

    drawback_act = fields.Char(string="Drawback Act")
    drawback_coefficient = fields.Float(string="Drawback Reduction Coefficient")

    # II - Imposto de Importação
    ii_base = fields.Monetary(
        string="II Base", currency_field="company_currency_id"
    )
    ii_rate = fields.Float(string="II Rate (%)")
    ii_reduced_rate = fields.Float(string="II Reduced Rate (%)")
    ii_reduction_percent = fields.Float(string="II Reduction (%)")
    ii_calculated_value = fields.Monetary(
        string="II Calculated", currency_field="company_currency_id"
    )
    ii_due_value = fields.Monetary(
        string="II Due", currency_field="company_currency_id"
    )
    ii_value = fields.Monetary(
        string="II Paid", currency_field="company_currency_id"
    )
    ii_regime_code = fields.Char(string="II Regime Code")
    ii_legal_basis_code = fields.Char(string="II Legal Basis Code")
    ii_tariff_agreement_code = fields.Char(string="II Tariff Agreement Code")

    # IPI
    ipi_base = fields.Monetary(
        string="IPI Base", currency_field="company_currency_id"
    )
    ipi_rate = fields.Float(string="IPI Rate (%)")
    ipi_reduced_rate = fields.Float(string="IPI Reduced Rate (%)")
    ipi_calculated_value = fields.Monetary(
        string="IPI Calculated", currency_field="company_currency_id"
    )
    ipi_value = fields.Monetary(
        string="IPI Paid", currency_field="company_currency_id"
    )
    ipi_regime_code = fields.Char(string="IPI Regime Code")

    # PIS / COFINS
    pis_cofins_base = fields.Monetary(
        string="PIS/COFINS Base", currency_field="company_currency_id"
    )
    pis_rate = fields.Float(string="PIS Rate (%)")
    pis_reduced_rate = fields.Float(string="PIS Reduced Rate (%)")
    pis_value = fields.Monetary(
        string="PIS Paid", currency_field="company_currency_id"
    )
    cofins_rate = fields.Float(string="COFINS Rate (%)")
    cofins_reduced_rate = fields.Float(string="COFINS Reduced Rate (%)")
    cofins_value = fields.Monetary(
        string="COFINS Paid", currency_field="company_currency_id"
    )
    pis_cofins_regime_code = fields.Char(string="PIS/COFINS Regime Code")

    # CIDE
    cide_rate = fields.Float(string="CIDE Rate")
    cide_due_value = fields.Monetary(
        string="CIDE Due", currency_field="company_currency_id"
    )
    cide_value = fields.Monetary(
        string="CIDE Paid", currency_field="company_currency_id"
    )

    # DCR (drawback)
    dcr_identification = fields.Char(string="DCR Identification")
    dcr_reduction_coefficient = fields.Float(string="DCR Reduction Coefficient")
    dcr_due_value = fields.Monetary(
        string="DCR Due", currency_field="company_currency_id"
    )

    line_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.import.declaration.addition.line",
        inverse_name="addition_id",
        string="Goods",
    )
    adjustment_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.import.declaration.adjustment",
        inverse_name="addition_id",
        string="Adjustments",
    )
    extra_field_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.import.declaration.field",
        inverse_name="addition_id",
        string="Unmapped Addition Fields",
    )
    fiscal_line_ids = fields.Many2many(
        comodel_name="l10n_br_fiscal.document.line",
        relation="l10n_br_fiscal_import_decl_addition_line_rel",
        string="Bill/Fiscal Lines",
    )


class ImportDeclarationAdditionLine(models.Model):
    _name = "l10n_br_fiscal.import.declaration.addition.line"
    _description = "Import Declaration Good (Mercadoria)"
    _order = "sequence"

    addition_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.import.declaration.addition",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    product_code = fields.Char(string="Product Code")
    description = fields.Char(string="Description")
    quantity = fields.Float(string="Quantity")
    unit_value = fields.Float(string="Unit Value", digits="Product Price")
    uom_name = fields.Char(string="Unit of Measure")
    statistical_quantity = fields.Float(string="Statistical Quantity")
    statistical_uom_name = fields.Char(string="Statistical UoM")
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Matched Product",
        help="Resolved by the wizard's matching against the bill lines.",
    )


class ImportDeclarationPayment(models.Model):
    _name = "l10n_br_fiscal.import.declaration.payment"
    _description = "Import Declaration Payment (Pagamento)"
    _order = "sequence"

    declaration_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.import.declaration",
        required=True,
        ondelete="cascade",
    )
    company_currency_id = fields.Many2one(
        related="declaration_id.company_currency_id"
    )
    sequence = fields.Integer(default=10)
    revenue_code = fields.Char(string="Revenue Code (Código Receita)")
    amount = fields.Monetary(
        string="Amount", currency_field="company_currency_id"
    )
    payment_type_code = fields.Char(string="Payment Type Code")
    bank_code = fields.Char(string="Bank Code")
    agency_code = fields.Char(string="Agency Code")
    account_number = fields.Char(string="Account Number")
    payment_date = fields.Date(string="Payment Date")


class ImportDeclarationAdjustment(models.Model):
    _name = "l10n_br_fiscal.import.declaration.adjustment"
    _description = "Import Declaration Adjustment (Acréscimo/Dedução)"
    _order = "sequence"

    addition_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.import.declaration.addition",
        required=True,
        ondelete="cascade",
    )
    company_currency_id = fields.Many2one(
        related="addition_id.company_currency_id"
    )
    sequence = fields.Integer(default=10)
    kind = fields.Selection(selection=ADJUSTMENT_KIND, required=True)
    code = fields.Char(string="Code")
    description = fields.Char(string="Description")
    amount_foreign = fields.Float(string="Amount (Foreign Currency)")
    amount_brl = fields.Monetary(
        string="Amount (BRL)", currency_field="company_currency_id"
    )


class ImportDeclarationDocument(models.Model):
    _name = "l10n_br_fiscal.import.declaration.document"
    _description = "Import Declaration Dispatch Document"
    _order = "sequence"

    declaration_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.import.declaration",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    type_code = fields.Char(string="Document Type Code")
    name = fields.Char(string="Document Name")
    number = fields.Char(string="Document Number")


class ImportDeclarationField(models.Model):
    _name = "l10n_br_fiscal.import.declaration.field"
    _description = "Import Declaration Unmapped Field"
    _order = "sequence"

    declaration_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.import.declaration",
        required=True,
        ondelete="cascade",
    )
    addition_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.import.declaration.addition",
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    record = fields.Char(
        string="Record",
        help="XML parent path, or the TXT record tag this field came from.",
    )
    tag = fields.Char(string="Tag")
    position = fields.Integer(string="Position")
    raw_value = fields.Char(string="Raw Value")


class ImportDeclarationDivergence(models.Model):
    _name = "l10n_br_fiscal.import.declaration.divergence"
    _description = "Import Declaration Reconciliation Divergence"
    _order = "severity desc, id"

    declaration_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.import.declaration",
        required=True,
        ondelete="cascade",
    )
    addition_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.import.declaration.addition",
        ondelete="cascade",
    )
    fiscal_line_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document.line",
        ondelete="cascade",
    )
    tax_domain = fields.Char(string="Tax Domain")
    dimension = fields.Selection(
        selection=[
            ("base", "Base"),
            ("percent", "Rate"),
            ("value", "Value"),
        ],
        required=True,
    )
    declared = fields.Float(string="Declared")
    computed = fields.Float(string="Computed")
    difference = fields.Float(string="Difference")
    severity = fields.Selection(
        selection=[
            ("rounding", "Rounding"),
            ("divergence", "Divergence"),
        ],
        required=True,
    )
    explanation = fields.Char(string="Explanation")
