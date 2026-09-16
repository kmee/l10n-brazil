# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models

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
