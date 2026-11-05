# Copyright (C) 2022-Today - Engenere (<https://engenere.one>).
# @author Antônio S. Pereira Neto <neto@engenere.one>
# @author Felipe Motter Pereira <felipe@engenere.one>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from unidecode import unidecode

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_br_account_payment_order.constants import TIPO_SERVICO


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

    def _check_cnab_pix_key_type(self):
        """Block the CNAB when a line leaves as PIX key without a key type mapping.

        Without the mapping the TIPO CHAVE field would be generated empty and the
        bank would reject the file (or pay the wrong key).
        """
        for bline in self:
            if (
                bline.cnab_payment_way_id.is_pix
                and not bline.cnab_pix_transfer_type_id
            ):
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
        "partner_id",
        "partner_bank_id",
        "partner_id.employee",
        "partner_pix_id",
        "partner_bank_id.bank_id",
        "partner_bank_id.bank_id.code_bc",
        "order_id.journal_id.bank_id",
        "order_id.payment_mode_id.cnab_structure_id",
    )
    def _compute_cnab_payment_way_id(self):
        for line in self:
            if line._cnab_freeze_exported():
                continue
            mode = line.order_id.payment_mode_id
            cnab_structure = line.order_id.cnab_structure_id
            rule = line._get_matching_rule()

            if rule:
                line.cnab_payment_way_id = rule.payment_way_id
                line.service_type = rule.service_type
            else:
                ways = mode.cnab_payment_way_ids.filtered(
                    lambda w, s=cnab_structure: w.cnab_structure_id == s
                )
                if ways:
                    line.cnab_payment_way_id = ways[0]
                    line.service_type = "20"
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
            self.cnab_payment_way_id = (
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
        self.ensure_one()
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
            return rule
        return False
