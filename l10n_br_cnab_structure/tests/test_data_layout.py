# Copyright (C) 2026-Today - KMEE (<http://kmee.com.br>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""Valida o layout das estruturas CNAB entregues no módulo.

Um arquivo CNAB é posicional: cada linha tem que ser preenchida por completo,
sem buraco e sem duas definições disputando a mesma posição. O modelo hoje só
verifica que o primeiro campo começa em 1 e o último termina em 240 — um campo
faltando no meio, ou duplicado, passa sem erro e vira arquivo rejeitado pelo
banco.

Este teste roda sobre os CSVs entregues, sem banco de dados, e é a trava que
impede uma estrutura nova (ou o ajuste de uma existente) entrar quebrada.

Sobre os grupos condicionais: cada grupo é incluído de forma independente,
conforme suas condições (``CNABLine.output()``). Grupos diferentes podem
definir as mesmas posições — são variantes mutuamente exclusivas, como
"conta no mesmo banco" e "conta em outro banco" — então isso não é conflito.
O que nunca pode acontecer é:

* um campo de grupo colidir com um campo sem grupo, que é sempre emitido;
* a união de tudo deixar uma posição sem definição nenhuma.
"""

import csv
import re
import unicodedata
import unittest
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MODULE_PREFIX = "l10n_br_cnab_structure."


def strip_module(xmlid):
    return xmlid[len(MODULE_PREFIX) :] if xmlid.startswith(MODULE_PREFIX) else xmlid


def ref_name(name, start_pos, end_pos):
    """Reproduz ``CNABField._compute_ref_name``.

    É por esse nome que ``CnabLine.sorted_values()`` indexa os campos, então
    dois campos com o mesmo ref_name emitidos juntos são colapsados em
    silêncio na geração do arquivo.
    """
    slug = unicodedata.normalize("NFKD", (name or "").replace(" ", "_").lower())
    slug = slug.encode("ascii", "ignore").decode("ascii")
    return f"{start_pos}_{end_pos}_{slug}"


def read_csv(filename):
    with open(DATA_DIR / filename, encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def positions(field):
    return int(field["start_pos"]), int(field["end_pos"])


class TestCNABDataLayout(unittest.TestCase):
    """Trava de layout sobre os dados entregues pelo módulo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structures = {
            strip_module(row["id"]): row
            for row in read_csv("l10n_br_cnab.structure.csv")
        }
        cls.lines = {
            strip_module(row["id"]): row for row in read_csv("l10n_br_cnab.line.csv")
        }
        cls.groups = {
            strip_module(row["id"]): row
            for row in read_csv("cnab.line.field.group.csv")
        }
        cls.fields_by_line = defaultdict(list)
        for row in read_csv("l10n_br_cnab.line.field.csv"):
            cls.fields_by_line[strip_module(row["cnab_line_id/id"])].append(row)

    # -- helpers ---------------------------------------------------------

    def _line_length(self, line_id):
        """Tamanho da linha, deduzido do formato CNAB da estrutura."""
        structure_id = strip_module(self.lines[line_id]["cnab_structure_id/id"])
        payment_method = self.structures[structure_id]["payment_method_id/id"]
        match = re.search(r"cnab(\d{3})", payment_method)
        self.assertTrue(
            match,
            f"Não foi possível deduzir o formato CNAB de {structure_id} "
            f"a partir de {payment_method!r}.",
        )
        return int(match.group(1))

    def _group_name(self, group_id):
        return self.groups.get(group_id, {}).get("name") or group_id

    def _split_by_group(self, fields):
        """Separa os campos sempre emitidos dos campos de cada grupo."""
        ungrouped = [f for f in fields if not f["cnab_group_id/id"]]
        grouped = defaultdict(list)
        for field in fields:
            if field["cnab_group_id/id"]:
                grouped[strip_module(field["cnab_group_id/id"])].append(field)
        return ungrouped, grouped

    def _emitted_sets(self, fields):
        """Conjuntos de campos que podem ser emitidos juntos.

        Sem grupos, é um conjunto só. Com grupos, é o conjunto sempre emitido
        combinado com cada grupo — que é o que precisa ser consistente.
        """
        ungrouped, grouped = self._split_by_group(fields)
        if not grouped:
            return [("sem grupo condicional", ungrouped)]
        return [
            (self._group_name(group_id), ungrouped + group_fields)
            for group_id, group_fields in sorted(grouped.items())
        ]

    # -- testes ----------------------------------------------------------

    def test_no_field_collision(self):
        """Nada pode disputar posição com um campo que é sempre emitido."""
        for line_id, fields in sorted(self.fields_by_line.items()):
            for set_name, emitted in self._emitted_sets(fields):
                context = f"{line_id} (com o grupo {set_name!r})"
                occupied = {}
                for field in sorted(emitted, key=positions):
                    start, end = positions(field)
                    self.assertLessEqual(
                        start,
                        end,
                        f"{context}: {field['id']} começa depois de terminar.",
                    )
                    for position in range(start, end + 1):
                        if position in occupied:
                            self.fail(
                                f"{context}: a posição {position} é definida por "
                                f"{occupied[position]!r} e por {field['id']!r}. "
                                f"Só um dos dois pode existir."
                            )
                        occupied[position] = field["id"]

    def test_no_duplicated_ref_name(self):
        """Campos com o mesmo ref_name se anulam sem aviso na geração."""
        for line_id, fields in sorted(self.fields_by_line.items()):
            for set_name, emitted in self._emitted_sets(fields):
                seen = {}
                for field in emitted:
                    key = ref_name(field["name"], *positions(field))
                    if key in seen:
                        self.fail(
                            f"{line_id} (com o grupo {set_name!r}): {seen[key]!r} e "
                            f"{field['id']!r} têm o mesmo ref_name ({key!r}). Na "
                            f"geração um sobrescreve o outro em silêncio."
                        )
                    seen[key] = field["id"]

    def test_line_is_fully_covered(self):
        """A união de todos os campos precisa cobrir a linha inteira."""
        for line_id, fields in sorted(self.fields_by_line.items()):
            length = self._line_length(line_id)
            covered = set()
            for field in fields:
                start, end = positions(field)
                covered.update(range(start, end + 1))
            missing = sorted(set(range(1, length + 1)) - covered)
            self.assertFalse(
                missing,
                f"{line_id}: posições sem nenhum campo definido: "
                f"{self._as_ranges(missing)} (a linha tem {length} posições).",
            )
            extra = sorted(position for position in covered if position > length)
            self.assertFalse(
                extra,
                f"{line_id}: posições além do tamanho da linha ({length}): "
                f"{self._as_ranges(extra)}.",
            )

    @staticmethod
    def _as_ranges(numbers):
        """Compacta [1,2,3,7] em '1-3, 7' para a mensagem de erro."""
        ranges = []
        for number in numbers:
            if ranges and number == ranges[-1][1] + 1:
                ranges[-1][1] = number
            else:
                ranges.append([number, number])
        return ", ".join(
            str(start) if start == end else f"{start}-{end}" for start, end in ranges
        )
