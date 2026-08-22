# Copyright (C) 2026-Today - KMEE (<http://kmee.com.br>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""Infraestrutura de testes *golden* para as saídas CNAB.

Um golden é a saída de um banco (payload ou arquivo) congelada e commitada no
repositório. A partir daí, qualquer alteração que mude o que é enviado para
aquele banco aparece como diff no golden dele.

O objetivo é responder de forma barata à pergunta que hoje não tem resposta:
*"o ajuste que eu fiz para o banco X altera algum outro banco?"*. Se o PR
altera apenas o golden do banco X, não altera. Se altera o golden de outro
banco, ou é bug ou é uma mudança de base que precisa estar explícita.

Como semear/atualizar um golden::

    UPDATE_GOLDEN=1 odoo --test-enable -i l10n_br_account_payment_brcobranca ...

Ao semear, cada golden é gerado **duas vezes** e as duas execuções precisam
bater. Isso garante que o golden é determinístico: se sobrou no payload uma
data de "hoje", uma sequência ou um id de banco de dados, o teste falha na
hora de gravar em vez de virar um falso positivo intermitente depois.
"""

import json
import logging
import os

_logger = logging.getLogger(__name__)

UPDATE_GOLDEN_ENV = "UPDATE_GOLDEN"

_SEED_INSTRUCTIONS = (
    "Golden ausente: %(path)s\n"
    "Gere-o com a variável de ambiente %(env)s=1 e confira o resultado contra "
    "um arquivo homologado pelo banco antes de commitar."
)

_NOT_DETERMINISTIC = (
    "O golden '%(name)s' não é determinístico: duas gerações seguidas "
    "produziram saídas diferentes, então ele não pode ser congelado.\n"
    "%(diff)s\n"
    "Fixe no teste o que varia (data do documento, nosso número, número do "
    "documento, sequencial do arquivo, horário de geração) antes de semear."
)


class GoldenMixin:
    """Compara a saída de um banco com uma referência congelada em disco.

    A classe de teste precisa implementar :meth:`_golden_dir`, retornando o
    ``pathlib.Path`` do diretório onde ficam os goldens daquele módulo.
    """

    def _golden_dir(self):
        raise NotImplementedError(
            "Defina _golden_dir() retornando o diretório de goldens do módulo."
        )

    def _golden_path(self, name, ext):
        return self._golden_dir() / f"{name}.{ext}"

    # -- serialização ----------------------------------------------------

    @staticmethod
    def _dump_json(value):
        return (
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=str)
            + "\n"
        )

    @staticmethod
    def _dump_text(value):
        return value

    # -- API pública -----------------------------------------------------

    def assert_golden_json(self, name, produce):
        """Congela um payload (dict/list) em JSON.

        :param name: nome do caso, ex.: ``033_santander_240``
        :param produce: callable sem argumentos que devolve o payload
        """
        self._assert_golden(name, "json", produce, self._dump_json)

    def assert_golden_text(self, name, produce, ext="rem"):
        """Congela um arquivo texto (a remessa posicional, por exemplo)."""
        self._assert_golden(name, ext, produce, self._dump_text)

    # -- implementação ---------------------------------------------------

    def _assert_golden(self, name, ext, produce, dump):
        path = self._golden_path(name, ext)
        current = dump(produce())

        if os.environ.get(UPDATE_GOLDEN_ENV):
            second = dump(produce())
            if second != current:
                raise AssertionError(
                    _NOT_DETERMINISTIC
                    % {
                        "name": name,
                        "diff": self.describe_text_diff(current, second),
                    }
                )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(current.encode("utf-8"))
            _logger.warning("Golden gravado: %s", path)
            return

        if not path.exists():
            self.skipTest(_SEED_INSTRUCTIONS % {"path": path, "env": UPDATE_GOLDEN_ENV})

        expected = path.read_bytes().decode("utf-8")
        self.maxDiff = None
        self.assertEqual(
            expected,
            current,
            f"A saída do caso '{name}' mudou em relação ao golden.\n"
            f"{self.describe_text_diff(expected, current)}\n"
            f"Se a mudança é esperada, regrave com "
            f"{UPDATE_GOLDEN_ENV}=1 e justifique no PR.",
        )

    @staticmethod
    def describe_text_diff(expected, current):
        """Descreve a primeira divergência em termos de linha e coluna.

        Em arquivo posicional isso é o que interessa: saber que mudou a
        posição 154 da linha 3 vale mais do que um diff de texto corrido.
        """
        expected_lines = expected.splitlines()
        current_lines = current.splitlines()
        for index, (exp_line, cur_line) in enumerate(
            zip(expected_lines, current_lines, strict=False), 1
        ):
            if exp_line == cur_line:
                continue
            column = next(
                (
                    pos
                    for pos, (exp_char, cur_char) in enumerate(
                        zip(exp_line, cur_line, strict=False), 1
                    )
                    if exp_char != cur_char
                ),
                min(len(exp_line), len(cur_line)) + 1,
            )
            start = max(column - 1, 0)
            end = start + 20
            return (
                f"Primeira divergência na linha {index}, posição {column}:\n"
                f"  golden: {exp_line[start:end]!r}\n"
                f"  atual : {cur_line[start:end]!r}"
            )
        if len(expected_lines) != len(current_lines):
            return (
                f"Quantidade de linhas mudou: golden {len(expected_lines)}, "
                f"atual {len(current_lines)}."
            )
        return "As saídas diferem apenas em espaços/quebras de linha finais."
