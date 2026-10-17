# Copyright (C) 2022-Today - Engenere (<https://engenere.one>).
# @author Antônio S. Pereira Neto <neto@engenere.one>
# @author Felipe Motter Pereira <felipe@engenere.one>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from unidecode import unidecode

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_br_account_payment_order.barcode_utils import (
    barcode_value,
    clean_digits,
)
from odoo.addons.l10n_br_account_payment_order.constants import (
    PAGAMENTO_CONTAS_TRIBUTOS_IMPOSTOS,
    PAGAMENTO_FORNECEDOR,
    TIPO_SERVICO,
)

# Payment way codes (FEBRABAN layout) that credit a bank account: credit in
# checking/savings account, DOC and TED
CNAB_ACCOUNT_PAYMENT_WAY_CODES = ("01", "03", "05", "06", "07", "41", "43")

# Itau SISPAG manual v085 (note 4 and table of p. 4): payment ways of taxes
# (GPS, DARF, GARE, IPVA, DPVAT, FGTS and taxes with barcode) require service
# type 22. Concessionarias (13) stay 20. DARJ (21) does not exist in v085.
ITAU_TAX_PAYMENT_WAY_CODES = ("16", "17", "18", "19", "22", "25", "27", "35", "91")
ITAU_BANK_CODE = "341"

# Payment ways whose batch carries segment J-52 (boleto beneficiary inscription)
CNAB_BOLETO_J52_WAY_CODES = ("30", "31")

# Itau SISPAG manual v085 (table of p. 4 and note 4 of p. 46): the payment type
# 30 (Salarios) accepts exclusively the way 01 (credit in Itau checking account)
# or 60 (cartao salario); DOC, TED, OP, cheque and the other ways are rejected
# with the return code IM (TIPO X FORMA NAO COMPATIVEL).
ITAU_SALARY_PAYMENT_WAY_CODES = ("01", "60")


class CnabGroupedPaymentLine:
    """Read-only view of several payment lines paying the same barcode.

    Exposes the first line (its name is the "seu numero" sent to the bank) with
    ``amount_currency`` replaced by the sum of the grouped lines, so the CNAB
    field expressions need no change. The grouped records are in ``lines``.
    """

    def __init__(self, lines, amount):
        self.lines = lines
        self._main = lines[0]
        self.amount_currency = amount

    def __getattr__(self, name):
        return getattr(self._main, name)


class AccountPaymentLine(models.Model):
    """
    Override Payment Line
    for add Help Functions for CNAB implementation.
    """

    _inherit = "account.payment.line"

    cnab_pix_type_id = fields.Many2one(
        comodel_name="cnab.pix.key.type",
        compute="_compute_cnab_pix_type_id",
        store=False,
    )

    cnab_beneficiary_name = fields.Char(
        compute="_compute_cnab_beneficiary_name",
        help="Name of the beneficiary (Nome do Favorecido) that will be informed"
        " in the CNAB.",
    )

    cnab_pix_transfer_type_id = fields.Many2one(
        comodel_name="cnab.pix.transfer.type",
        compute="_compute_cnab_pix_transfer_type_id",
        store=False,
    )

    cnab_payment_way_id = fields.Many2one(
        comodel_name="cnab.payment.way",
        compute="_compute_cnab_payment_way_id",
        store=True,
    )

    batch_template_id = fields.Many2one(
        comodel_name="l10n_br_cnab.batch",
        compute="_compute_batch_template_id",
    )

    service_type = fields.Selection(
        selection=TIPO_SERVICO,
        compute="_compute_cnab_payment_way_id",
        store=True,
    )

    @api.depends("partner_pix_id", "partner_pix_id.key_type")
    def _compute_cnab_pix_type_id(self):
        for bline in self:
            cnab_pix_type_id = (
                bline.order_id.cnab_structure_id.cnab_pix_key_type_ids.filtered(
                    lambda t, b=bline: t.key_type == b.partner_pix_id.key_type
                )
            )
            bline.cnab_pix_type_id = cnab_pix_type_id

    @api.depends("pix_transfer_type", "partner_pix_id", "cnab_payment_way_id.is_pix")
    def _compute_cnab_pix_transfer_type_id(self):
        for bline in self:
            transfer_domain = False
            if bline.payment_mode_domain == "pix_transfer":
                transfer_domain = bline.pix_transfer_type
            elif bline.cnab_payment_way_id.is_pix and bline.partner_pix_id:
                # PIX way chosen by a CNAB payment rule on a payment mode that
                # is not a PIX transfer mode (e.g. salary by PIX key).
                transfer_domain = "pix_key"
            if transfer_domain:
                bline.cnab_pix_transfer_type_id = self.env[
                    "cnab.pix.transfer.type"
                ].search(
                    [
                        ("cnab_structure_id", "=", bline.order_id.cnab_structure_id.id),
                        ("type_domain", "=", transfer_domain),
                    ],
                    limit=1,
                )
            else:
                bline.cnab_pix_transfer_type_id = False

    def _cnab_line_requires_bank_account(self):
        """Also consider the CNAB payment way of the line (credit in account,
        TED and DOC codes of the FEBRABAN layout), PIX ways need the account only
        when leaving without PIX key."""
        self.ensure_one()
        if super()._cnab_line_requires_bank_account():
            return True
        way = self.cnab_payment_way_id
        if not way or self.payment_mode_domain == "boleto":
            return False
        if way.is_pix:
            return not self.partner_pix_id
        return way.code in CNAB_ACCOUNT_PAYMENT_WAY_CODES

    def _cnab_line_requires_favored_inscription(self):
        """Also consider the CNAB payment way of the line: credit in account,
        TED/DOC, PIX and the boleto ways that carry segment J-52."""
        self.ensure_one()
        way = self.cnab_payment_way_id
        if not way:
            return super()._cnab_line_requires_favored_inscription()
        return (
            way.is_pix
            or way.code in CNAB_ACCOUNT_PAYMENT_WAY_CODES
            or way.code in CNAB_BOLETO_J52_WAY_CODES
        )

    def _get_cnab_barcode_kind(self):
        """Return ``(kind, preferred ways, wrong ways)`` of the barcode of the line.

        ``kind`` is "same" (boleto of the paying bank), "other" (boleto of
        another bank) or "utility"; False without barcode. ``wrong`` are the
        ways that would put the barcode in a layout of another kind.
        """
        self.ensure_one()
        code = clean_digits(self.barcode or self.digitable_line)
        if not code:
            return False, (), ()
        if code[0] == "8":
            return "utility", ("13", "91"), ("30", "31")
        bank = self._normalize_cnab_bank_code(code[:3])
        payer = self._normalize_cnab_bank_code(self.order_id.journal_id.bank_id.code_bc)
        if bank and bank == payer:
            return "same", ("30",), ("31",)
        return "other", ("31",), ("30",)

    def _check_cnab_barcode_way(self):
        """Block a barcode paid in the way of another bank/kind.

        With the preferred way missing from the payment mode the line falls on
        the first way of the mode (e.g. one-way mode "30" with a barcode of
        another bank, or the reverse): the bank rejects the file (bank 341 in
        way 31, other bank in way 30, utility in 30/31). Mixed modes (all the
        ways configured) never reach it.
        """
        for line in self:
            kind, preferred, wrong = line._get_cnab_barcode_kind()
            way = line.cnab_payment_way_id
            if not kind or not way or way.code not in wrong:
                continue
            modes = self.env["account.payment.mode"].search(
                [
                    ("company_id", "=", line.order_id.company_id.id),
                    ("payment_order_ok", "=", True),
                    ("payment_mode_domain", "=", "boleto"),
                    ("cnab_structure_id", "=", line.order_id.cnab_structure_id.id),
                ]
            )
            suggestion = modes.filtered(
                lambda m, p=preferred: any(
                    w.code in p and w.batch_id for w in m.cnab_payment_way_ids
                )
            )[:1]
            raise UserError(
                _(
                    "The barcode of payment line %(line)s (partner: %(partner)s) "
                    "is %(kind)s, which must be paid in way %(preferred)s, but "
                    "the payment mode %(mode)s only has way %(way)s and the bank "
                    "would reject the file. Use %(suggestion)s for this line.",
                    line=line.name or line.display_name,
                    partner=line.partner_id.display_name or "-",
                    kind={
                        "same": _("a boleto of the paying bank"),
                        "other": _("a boleto of another bank"),
                        "utility": _("a utility/tax bill"),
                    }[kind],
                    preferred=" / ".join(preferred),
                    mode=line.order_id.payment_mode_id.display_name,
                    way=way.code,
                    suggestion=(
                        _("the payment mode %s", suggestion.display_name)
                        if suggestion
                        else _("a payment mode that has way %s", preferred[0])
                    ),
                )
            )

    def _check_cnab_service_type_way(self):
        """Block Itau salary (service type 30) in a way other than 01/60.

        Itau SISPAG manual v085, table of p. 4 and note 4 of p. 46: the type 30
        accepts exclusively the way 01 (credit in Itau account) or 60 (cartao
        salario); other ways are rejected by the bank (return code IM).
        """
        for line in self:
            way = line.cnab_payment_way_id
            if (
                line.order_id.cnab_structure_id.bank_id.code_bc != ITAU_BANK_CODE
                or line.service_type != "30"
                or not way
                or way.code in ITAU_SALARY_PAYMENT_WAY_CODES
            ):
                continue
            raise UserError(
                _(
                    "Payment line %(line)s (partner: %(partner)s) is a salary "
                    "payment (service type 30) in way %(way)s. Itau only accepts "
                    "salary by credit in Itau account (way 01) or cartao salario "
                    "(60); the bank would reject it as incompatible type x way. "
                    "Pay the partner by credit in an Itau account or change the "
                    "CNAB payment rule to service type 20.",
                    line=line.name or line.display_name,
                    partner=line.partner_id.display_name or "-",
                    way=way.code,
                )
            )

    def draft2open_payment_line_check(self):
        """Also block barcode in the wrong way and salary in an Itau non credit way."""
        res = super().draft2open_payment_line_check()
        self._check_cnab_barcode_way()
        self._check_cnab_service_type_way()
        return res

    def _cnab_group_by_barcode(self):
        """Group lines that pay the same barcode (one boleto for N bills).

        Returns the list of records to export: lines with a unique barcode
        (or none) as they are, and one CnabGroupedPaymentLine for each barcode
        shared by several lines, with the summed amount. When the barcode
        carries a value the sum must be equal to it.
        """
        groups = {}
        for line in self:
            # lines of different partners with the same barcode are detected
            # (and blocked) below, never merged silently
            key = clean_digits(line.barcode or line.digitable_line) or line.id
            groups[key] = groups.get(key, self.browse()) | line
        result = []
        for key, lines in groups.items():
            if len(lines) == 1:
                result.append(lines)
                continue
            names = ", ".join(lines.mapped(lambda x: x.name or ""))
            if len(lines.partner_id) > 1:
                raise UserError(
                    _(
                        "The payment lines %(lines)s have the same barcode but "
                        "different partners. A boleto belongs to one payee: fix "
                        "the barcode or the partner of the lines.",
                        lines=names,
                    )
                )
            total = sum(lines.mapped("amount_currency"))
            value = barcode_value(key)
            if value is None:
                raise UserError(
                    _(
                        "The payment lines %(lines)s share the same barcode and "
                        "it does not carry a value (open amount boleto), so the "
                        "total to pay cannot be checked. Pay them in separate "
                        "orders or join the bills in a single payment line.",
                        lines=names,
                    )
                )
            if lines[0].currency_id.compare_amounts(total, float(value)):
                # Discount, interest and fine of the lines are not exported for
                # a grouped boleto (J 115-144 would carry only the first line),
                # so no adjustment is allowed: the sum must be the barcode value.
                raise UserError(
                    _(
                        "The payment lines %(lines)s share the same barcode, whose "
                        "value is %(value)s, but their amounts sum %(total)s. "
                        "Interest, fine and discount are not applied to a boleto "
                        "paid by several lines: adjust the amounts so that they "
                        "sum the value of the boleto, or pay the lines separately "
                        "(remove the repeated barcode).",
                        lines=names,
                        value=value,
                        total=total,
                    )
                )
            result.append(CnabGroupedPaymentLine(lines, total))
        return result

    def _check_cnab_pix_key_type(self):
        """Block the CNAB when a line leaves as PIX key without a key type mapping.

        Without the mapping the TIPO CHAVE field would be generated empty and the
        bank would reject the file (or pay the wrong key).
        """
        for bline in self:
            if (
                bline.cnab_payment_way_id.is_pix
                and not bline.cnab_pix_transfer_type_id
                and bline.partner_pix_id
            ):
                raise UserError(
                    _(
                        "Não foi possível gerar o arquivo CNAB: %(partner)s tem "
                        "chave PIX, mas a estrutura CNAB %(structure)s não possui "
                        "mapeamento do tipo de transferência PIX por chave. Corrija "
                        "a configuração da estrutura CNAB.",
                        partner=bline.partner_id.name,
                        structure=bline.order_id.cnab_structure_id.display_name,
                    )
                )
            if bline.cnab_payment_way_id.is_pix and not bline.cnab_pix_transfer_type_id:
                raise UserError(
                    _(
                        "Não foi possível gerar o arquivo CNAB: %(partner)s foi "
                        "enquadrado(a) em uma forma de pagamento PIX, mas não "
                        "possui chave PIX cadastrada. Cadastre a chave PIX ou "
                        "ajuste a regra de pagamento CNAB.",
                        partner=bline.partner_id.name,
                    )
                )
            if (
                bline.partner_pix_id
                and bline.cnab_pix_transfer_type_id.type_domain == "pix_key"
                and not bline.cnab_pix_type_id
            ):
                key_type = bline.partner_pix_id.key_type
                label = dict(
                    bline.partner_pix_id._fields["key_type"]._description_selection(
                        self.env
                    )
                ).get(key_type, key_type)
                raise UserError(
                    _(
                        "Não foi possível gerar o arquivo CNAB: a chave PIX de "
                        "%(partner)s é do tipo '%(key_type)s', que não possui "
                        "mapeamento na estrutura CNAB %(structure)s. Corrija o "
                        "cadastro da chave PIX do parceiro.",
                        partner=bline.partner_id.name,
                        key_type=label,
                        structure=bline.order_id.cnab_structure_id.display_name,
                    )
                )

    def _compute_cnab_beneficiary_name(self):
        for bline in self:
            if bline.partner_bank_id and bline.partner_bank_id.acc_holder_name:
                bline.cnab_beneficiary_name = unidecode(
                    bline.partner_bank_id.acc_holder_name
                ).strip()
            else:
                bline.cnab_beneficiary_name = unidecode(bline.partner_id.name).strip()

    def _compute_batch_template_id(self):
        for bline in self:
            if not bline.cnab_payment_way_id.batch_id:
                raise UserError(_("Mapping for batch template not found"))
            bline.batch_template_id = bline.cnab_payment_way_id.batch_id

    @api.depends(
        "payment_mode_id",
        "payment_mode_id.payment_mode_domain",
        "partner_id",
        "partner_bank_id",
        "partner_id.employee",
        "partner_pix_id",
        "partner_bank_id.bank_id",
        "partner_bank_id.bank_id.code_bc",
        "barcode",
        "digitable_line",
        "order_id.journal_id.bank_id",
        "order_id.payment_mode_id.cnab_structure_id",
    )
    def _compute_cnab_payment_way_id(self):
        for line in self:
            if line._cnab_freeze_exported():
                continue
            mode = line.order_id.payment_mode_id
            cnab_structure = line.order_id.cnab_structure_id
            ways = mode.cnab_payment_way_ids.filtered(
                lambda w, s=cnab_structure: w.cnab_structure_id == s
            )
            # Lines with barcode: the way follows the barcode (30/31/13/91) and
            # no rule is evaluated, so a rule meant for TED/credit/salary (e.g.
            # same bank supplier -> 01) never hijacks a boleto.
            barcode_way = line._get_cnab_barcode_way(ways) if ways else False
            rule, skipped_rule = (
                (False, False) if barcode_way else line._match_cnab_rule()
            )

            if barcode_way:
                line.cnab_payment_way_id = barcode_way
                line.service_type = line._get_cnab_default_service_type(barcode_way)
            elif rule:
                line.cnab_payment_way_id = rule.payment_way_id
                line.service_type = rule.service_type
            else:
                if ways:
                    line.cnab_payment_way_id = ways[0]
                    # rules refused for the mode still say the service type
                    # (e.g. salary 30) of the payee
                    line.service_type = (
                        skipped_rule.service_type
                        if skipped_rule
                        else line._get_cnab_default_service_type(ways[0])
                    )
                else:
                    line.cnab_payment_way_id = False
                    line.service_type = False
                    if mode.cnab_structure_ok:
                        raise UserError(
                            _(
                                "CNAB payment way not found.\n"
                                "Payment Mode: %(payment_mode)s\n"
                                "CNAB Structure: %(cnab_structure)s"
                            )
                            % {
                                "payment_mode": mode.name,
                                "cnab_structure": cnab_structure.name,
                            }
                        )

    def _get_cnab_default_service_type(self, way):
        """Service type (tipo de pagamento) of a way chosen without payment rule.

        20 (fornecedor), except the tax ways of Itau that require 22. Mapped by
        way code, so no new field is needed; a payment rule keeps deciding its
        own service type.
        """
        self.ensure_one()
        structure = self.order_id.cnab_structure_id
        if (
            structure.bank_id.code_bc == ITAU_BANK_CODE
            and way.code in ITAU_TAX_PAYMENT_WAY_CODES
        ):
            return PAGAMENTO_CONTAS_TRIBUTOS_IMPOSTOS
        return PAGAMENTO_FORNECEDOR

    def _get_cnab_barcode_way(self, ways):
        """Pick the payment way of a line with barcode, among ``ways``.

        Takes precedence over the payment rules for lines with barcode. Keyed
        by the FEBRABAN way code, so it works with any structure that has them:

        * utility/tax barcode (starts with 8): the 2nd digit is the segment.
          Tributos (1 prefeituras, 5 orgaos governamentais, 7 multas) prefer 91
          (tributos com codigo de barras), then 13; the others (2 saneamento,
          3 energia/gas, 4 telecom, 6, 9) prefer 13 (concessionarias), then 91;
        * banking boleto of the paying bank (341 and 409 are the same bank): 30;
        * banking boleto of another bank: 31.

        Ways without batch template are skipped (not exportable). Returns an
        empty recordset when the line has no barcode or no preferred way is
        configured in the payment mode (caller keeps its previous behavior).
        """
        self.ensure_one()
        code = clean_digits(self.barcode or self.digitable_line)
        if not code:
            return ways.browse()
        if code[0] == "8":
            if len(code) > 1 and code[1] in ("1", "5", "7"):
                preferred = ("91", "13")
            else:
                preferred = ("13", "91")
        else:
            bank = self._normalize_cnab_bank_code(code[:3])
            payer = self._normalize_cnab_bank_code(
                self.order_id.journal_id.bank_id.code_bc
            )
            preferred = ("30",) if bank and bank == payer else ("31",)
        for wanted in preferred:
            way = ways.filtered(lambda w, c=wanted: w.code == c and w.batch_id)[:1]
            if way:
                return way
        return ways.browse()

    def _cnab_freeze_exported(self):
        """Keep stored service type and payment way of exported orders.

        Lines of orders that are not draft/open (generated, uploaded, done,
        cancel) keep the values already stored, so a later change of flag, bank
        or employee never rewrites what went to the bank, and no error is
        raised for them. The stored columns are read with SQL to avoid
        recursing into the compute. Returns True when the line was frozen.
        """
        self.ensure_one()
        if not isinstance(self.id, int) or self.order_id.state in ("draft", "open"):
            return False
        self.env.cr.execute(
            "SELECT service_type, cnab_payment_way_id "
            "FROM account_payment_line WHERE id = %s",
            (self.id,),
        )
        row = self.env.cr.fetchone()
        if not row or not (row[0] or row[1]):
            return False
        self.service_type = row[0]
        if row[1]:
            self.cnab_payment_way_id = row[1]
        else:
            # Line exported before cnab_payment_way_id became stored (module
            # upgrade): fill only the missing way, never raise, and keep the
            # stored service type.
            rule = self._get_matching_rule()
            structure = self.order_id.cnab_structure_id
            ways = self.order_id.payment_mode_id.cnab_payment_way_ids.filtered(
                lambda w, s=structure: w.cnab_structure_id == s
            )
            barcode_way = self._get_cnab_barcode_way(ways)
            self.cnab_payment_way_id = barcode_way or (
                rule.payment_way_id if rule else (ways[:1] or False)
            )
        return True

    @api.model
    def _normalize_cnab_bank_code(self, code):
        """Bank code used to compare banks: 409 (Unibanco) is the same as 341."""
        code = (code or "").strip()
        return "341" if code == "409" else code

    def _get_cnab_bank_type(self):
        """Return "same" or "other" comparing bank codes, never record ids."""
        self.ensure_one()
        payee = self._normalize_cnab_bank_code(self.partner_bank_id.bank_id.code_bc)
        payer = self._normalize_cnab_bank_code(self.order_id.journal_id.bank_id.code_bc)
        return "same" if payee and payee == payer else "other"

    def _is_cnab_employee(self):
        """Whether the payee is an employee (salary payment).

        Base implementation only uses the res.partner.employee flag, the only
        source that exists without the hr module. The bridge module
        l10n_br_cnab_structure_hr adds the hr.employee detection.
        """
        self.ensure_one()
        return bool(self.partner_id.employee)

    def _get_matching_rule(self):
        """Finds the best matching CNAB rule based on bank and partner attributes."""
        return self._match_cnab_rule()[0]

    def _match_cnab_rule(self):
        """Return ``(rule, skipped_rule)``.

        ``rule`` is the best matching rule that fits the payment mode;
        ``skipped_rule`` is the first matching rule refused because it
        contradicts the mode (only meaningful when ``rule`` is empty).
        """
        self.ensure_one()
        skipped = False
        cnab_structure = self.order_id.cnab_structure_id
        bank_type = self._get_cnab_bank_type()
        partner_type = "employee" if self._is_cnab_employee() else "supplier"
        pix_key = "with_key" if self.partner_pix_id else "without_key"
        rules = self.env["l10n_br_cnab.payment.rule"].search(
            [
                ("cnab_structure_id", "=", cnab_structure.id),
            ]
        )
        for rule in rules:
            if rule.match_bank_type != "any" and rule.match_bank_type != bank_type:
                continue
            if (
                rule.match_partner_type != "any"
                and rule.match_partner_type != partner_type
            ):
                continue
            if rule.match_pix_key not in ("any", pix_key):
                continue
            if not self._cnab_rule_fits_payment_mode(rule):
                skipped = skipped or rule
                continue
            return rule, False
        return False, skipped

    def _cnab_rule_fits_payment_mode(self, rule):
        """Whether ``rule`` may take this line given its payment mode.

        Narrow on purpose: a PIX rule on a non-PIX mode (and the reverse) stays
        legitimate, e.g. salary by PIX key in a generic mode. Only the clear
        contradictions between the mode and the data of the line are refused:

        * PIX transfer mode, line with PIX key: a rule pointing to a way that is
          not PIX (credit in account 01, TED 41/43...) would drop the key and
          pay by account, so the rule is skipped;
        * TED/DOC mode, line with favored bank account and without PIX key: a
          PIX way rule is skipped (it would block generation, or send PIX
          without a key).

        When every matching rule is skipped the caller falls back to the first
        way of the payment mode.
        """
        self.ensure_one()
        way = rule.payment_way_id
        domain = self.payment_mode_domain
        if domain == "pix_transfer" and self.partner_pix_id:
            return way.is_pix
        if (
            domain in ("ted", "doc")
            and self.partner_bank_id
            and not self.partner_pix_id
        ):
            return not way.is_pix
        return True
