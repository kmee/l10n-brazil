# Copyright (C) 2026-Today - KMEE (<http://kmee.com.br>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""Impede que novos ``if`` de banco entrem no caminho comum do CNAB.

O framework de exportação já tem hooks por banco (``_prepare_remessa_<banco>``,
``_prepare_bank_line_<banco>``). O problema é que exceções de banco também
foram sendo escritas direto no fluxo genérico, na forma de comparações com o
código do banco. É isso que faz um ajuste para um banco poder quebrar outro, e
o que torna caro revisar um PR de banco.

Este teste é uma catraca: a lista abaixo é o inventário do que existe hoje e
só pode diminuir. Uma comparação nova falha o teste; uma comparação removida
também falha, pedindo que a lista seja atualizada — assim o inventário nunca
fica desatualizado e o progresso fica visível.

Ao encontrar este teste falhando por um caso novo: coloque a particularidade
no hook do banco correspondente em vez de no caminho comum.
"""

import re
import unittest
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SCANNED_MODULES = (
    "l10n_br_account_payment_brcobranca",
    "l10n_br_account_payment_order",
)

# Diretórios sem relação com o caminho de exportação.
IGNORED_PARTS = ("tests", "migrations")

# Ramificação por banco: comparação com o código do banco no Banco Central ou
# com o nome do banco no BRCobrança.
BANK_CONDITIONAL = re.compile(
    r"(?:code_bc|bank_name_brcobranca)\b\s*(?:==|!=|\bin\b|\bnot\s+in\b)"
)

# Inventário atual. Só pode diminuir.
KNOWN_BANK_CONDITIONALS = {
    (
        "l10n_br_account_payment_brcobranca/models/account_move_line.py",
        'if bank_account_id.bank_id.code_bc == "033":',
    ): 1,
    (
        "l10n_br_account_payment_brcobranca/models/account_move_line.py",
        'if bank_account_id.bank_id.code_bc == "136":',
    ): 1,
    (
        "l10n_br_account_payment_brcobranca/models/account_move_line.py",
        'if bank_account_id.bank_id.code_bc in ("021", "004"):',
    ): 1,
    (
        "l10n_br_account_payment_brcobranca/models/account_move_line.py",
        'if bank_account_id.bank_id.code_bc in ("748", "756"):',
    ): 1,
    (
        "l10n_br_account_payment_brcobranca/models/account_payment_line.py",
        'cnab_config.bank_code_bc == "001"',
    ): 1,
    (
        "l10n_br_account_payment_brcobranca/models/account_payment_line.py",
        'if cnab_config.bank_code_bc in ("085", "104", "033", "136") or (',
    ): 1,
    (
        "l10n_br_account_payment_brcobranca/parser/cnab_file_parser.py",
        'elif bank_name_brcobranca == "ailos":',
    ): 1,
    (
        "l10n_br_account_payment_brcobranca/parser/cnab_file_parser.py",
        'elif bank_name_brcobranca == "banco_brasil":',
    ): 2,
    (
        "l10n_br_account_payment_brcobranca/parser/cnab_file_parser.py",
        'elif self.bank.code_bc == "004" and cod_ocorrencia == "51":',
    ): 1,
    (
        "l10n_br_account_payment_brcobranca/parser/cnab_file_parser.py",
        'if bank_name_brcobranca in ("ailos", "santander"):',
    ): 2,
    (
        "l10n_br_account_payment_brcobranca/parser/cnab_file_parser.py",
        'if self.bank.code_bc == "341":',
    ): 2,
    (
        "l10n_br_account_payment_order/models/l10n_br_cnab_config.py",
        'self.bank_code_bc == "341"',
    ): 1,
}


def scan_bank_conditionals():
    """Inventaria as ramificações por banco nos módulos varridos."""
    found = Counter()
    for module in SCANNED_MODULES:
        module_path = REPO_ROOT / module
        if not module_path.is_dir():
            # Módulo ausente no caminho de addons: nada a varrer.
            continue
        for path in sorted(module_path.rglob("*.py")):
            relative = path.relative_to(REPO_ROOT)
            if set(relative.parts) & set(IGNORED_PARTS):
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if BANK_CONDITIONAL.search(line):
                    found[(relative.as_posix(), " ".join(line.split()))] += 1
    return found


class TestNoNewBankConditionals(unittest.TestCase):
    """Catraca sobre as ramificações por banco no caminho comum."""

    def test_no_new_bank_conditional(self):
        found = scan_bank_conditionals()
        if not found and not (REPO_ROOT / SCANNED_MODULES[0]).is_dir():
            self.skipTest("Módulos não encontrados a partir do diretório do teste.")

        new_entries = [
            (location, count - KNOWN_BANK_CONDITIONALS.get(location, 0))
            for location, count in sorted(found.items())
            if count > KNOWN_BANK_CONDITIONALS.get(location, 0)
        ]
        self.assertFalse(
            new_entries,
            "Nova ramificação por banco no caminho comum:\n"
            + "\n".join(
                f"  {path}: {expression}  (+{delta})"
                for (path, expression), delta in new_entries
            )
            + "\n\nCada banco tem um hook próprio "
            "(_prepare_remessa_<banco>, _prepare_bank_line_<banco>). "
            "Coloque a particularidade lá: no caminho comum ela vira risco "
            "para todos os outros bancos.",
        )

    def test_inventory_is_up_to_date(self):
        """A lista tem que refletir o que existe — senão ela mente."""
        found = scan_bank_conditionals()
        if not found and not (REPO_ROOT / SCANNED_MODULES[0]).is_dir():
            self.skipTest("Módulos não encontrados a partir do diretório do teste.")

        resolved = [
            (location, KNOWN_BANK_CONDITIONALS[location] - found.get(location, 0))
            for location in sorted(KNOWN_BANK_CONDITIONALS)
            if found.get(location, 0) < KNOWN_BANK_CONDITIONALS[location]
        ]
        self.assertFalse(
            resolved,
            "Ramificações por banco removidas (ótimo!). Atualize "
            "KNOWN_BANK_CONDITIONALS neste arquivo para que a catraca não "
            "afrouxe:\n"
            + "\n".join(
                f"  {path}: {expression}  (-{delta})"
                for (path, expression), delta in resolved
            ),
        )
