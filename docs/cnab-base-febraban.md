# Refatoração do framework CNAB: base FEBRABAN + bancos por cima

> Documento de proposta (RFC). Nenhum código de produção foi alterado ainda.
> Objetivo: discutir a arquitetura antes de mexer.

## 1. O problema, na prática

Hoje, quando alguém implementa/ajusta um banco no CNAB, não existe uma resposta
barata para a pergunta *"isso que eu fiz pode quebrar outro banco?"*. As razões
são três, e são independentes entre si:

1. **Dados duplicados**: no `l10n_br_cnab_structure` cada banco é uma cópia
   integral do layout, não uma especialização de uma base FEBRABAN.
2. **Código com `if` de banco no caminho comum**: no
   `l10n_br_account_payment_brcobranca` existem hooks por banco, mas as exceções
   também vivem espalhadas pelo fluxo genérico.
3. **Ausência de rede de segurança**: não há teste que compare a saída
   (bytes/payload) de cada banco com uma referência congelada. Sem isso,
   qualquer refatoração é feita no escuro — e a dúvida do item inicial nunca
   é respondida objetivamente.

As três camadas precisam ser tratadas. A terceira é a que de fato elimina a
dúvida; as duas primeiras é que tornam a manutenção sustentável.

## 2. Mapa atual

Convivem dois frameworks distintos:

| | `l10n_br_account_payment_brcobranca` | `l10n_br_cnab_structure` |
|---|---|---|
| Escopo | Cobrança/boleto (remessa 240/400/500 e retorno) | Pagamentos (e cobrança) 240/400/500 |
| Quem gera os bytes | Serviço Ruby BRCobrança (HTTP) | O próprio Odoo |
| O que o Odoo controla | O JSON enviado à API | Cada posição do arquivo |
| Especialização por banco | Hooks `_prepare_*_{banco}` + `if code_bc` | Uma estrutura completa por banco (registros) |

### 2.1 Onde estão os `if` de banco/carteira

| Arquivo | Linha | Decide por |
|---|---|---|
| `l10n_br_account_payment_brcobranca/models/account_payment_line.py` | 160-162 | `bank_code_bc in ("085","104","033","136")` ou `001` + 240 → `cod_desconto = "0"` |
| `l10n_br_account_payment_brcobranca/models/account_move_line.py` | 163 | `("021","004")` → `digito_conta_corrente` |
| " | 171 | `("748","756")` → `byte_idt`, `posto` |
| " | 179 | `"136"` → `conta_corrente_dv` |
| " | 187 | `"033"` → `convenio` |
| `l10n_br_account_payment_brcobranca/parser/cnab_file_parser.py` | 318 | `"004"` + ocorrência `51` → `not_accepted` |
| " | 392, 598 | `"341"` → nosso número sem DV |
| " | 326-340 | `_get_allowed_registration_code` por nome de banco |
| `l10n_br_account_payment_order/models/l10n_br_cnab_config.py` | 111 | `"341"` → carteira obrigatória |

Os hooks nomeados que já existem (`_prepare_remessa_{banco}`,
`_prepare_bank_line_{banco}`) estão corretos como ideia — o problema é que
**convivem** com os `if` acima e moram todos no mesmo arquivo compartilhado.

### 2.2 Quanto de duplicação existe no `l10n_br_cnab_structure`

Medido sobre os CSVs entregues (`data/l10n_br_cnab.line.field.csv`,
1.560 campos, 86 linhas, 4 estruturas 240):

```
campos por banco:  santander 589 | bb 338 | itaú 325 | sicoob 308
posições comuns às 4 estruturas: 234
   dessas, funcionalmente idênticas (tipo/default/origem/expressão): 146 (62%)
pares:  itaú×bb 75% | itaú×santander 73% | itaú×sicoob 74%
        bb×santander 67% | bb×sicoob 78% | santander×sicoob 67%
```

Ou seja: **cerca de 2/3 de cada estrutura é FEBRABAN puro, copiado 4 vezes.**

E parte do 1/3 restante não é diferença de banco — é *drift* de cópia:

* Header de pagamentos, filler 231-240: itaú `''`, bb `'0000000000'`,
  santander `''`, sicoob `'0'` — mesmo campo, quatro configurações.
* Header de tributos, posição 71: `alpha` nos três primeiros, `num` no sicoob.
* Santander e Sicoob têm os grupos condicionais *"Conta Corrente - Mesmo Banco"*
  e *"Outros Bancos"* **com condição e zero campos** — o andaime foi copiado do
  Itaú sem conteúdo (`cnab.line.field.group.csv` + `cnab.line.group.field.condition.csv`).
* BB, segmento A: o campo `DV CONTA` (42-42) existe duas vezes — uma sem grupo e
  outra em `group_1_bb`. Só não gera linha de 241 caracteres porque
  `CnabLine.sorted_values()` monta um `dict` por `ref_name` e **silenciosamente
  deduplica**. Se os dois campos tivessem nomes diferentes, o arquivo sairia
  errado sem nenhum erro.
* `CNABLine.check_line()` valida apenas que o primeiro campo começa em 1 e o
  último termina em 240 — **não valida buraco nem sobreposição no meio**.

Esse conjunto é exatamente o sintoma que motiva a refatoração: sem base comum,
cada correção só chega ao banco em que alguém percebeu o problema.

## 3. Princípio da proposta

> O framework nunca decide por banco. Ele resolve *uma vez* qual é a
> especialização e chama hooks. Banco novo = arquivo novo + registros novos +
> golden novo. Se um PR de banco precisa tocar em arquivo/estrutura
> compartilhada, isso é visível no diff e exige atualizar os goldens de todos.

Três trilhas, implementáveis de forma independente e nessa ordem de prioridade:

* **Trilha C — testes golden** (rede de segurança) → responde à pergunta.
* **Trilha B — adaptadores por banco** (código, brcobranca) → refatoração pura.
* **Trilha A — herança de estrutura** (dados, cnab_structure) → base FEBRABAN.

## 4. Trilha C — golden tests por banco (fazer primeiro)

Sem isso, as trilhas A e B são apostas. Com isso, viram refatorações verificáveis.

**Cobrança (brcobranca)**: os bytes são gerados pelo Ruby, mas o que o Odoo
controla — e onde estão todos os bugs de banco — é o JSON enviado à API. Então o
golden é o payload, e o teste roda 100% offline (hoje os testes dependem do
serviço e são pulados com `CI_NO_BRCOBRANCA`):

```
l10n_br_account_payment_brcobranca/tests/golden/
    001_banco_brasil_240.json
    001_banco_brasil_400.json
    033_santander_240.json
    033_santander_400.json
    ...
```

```python
def _assert_golden(self, case, payload):
    path = Path(__file__).parent / "golden" / f"{case}.json"
    payload = self._freeze(payload)     # sequencial_remessa, datas
    if os.environ.get("UPDATE_GOLDEN"):
        path.write_text(json.dumps(payload, indent=2, sort_keys=True,
                                   ensure_ascii=False))
    self.assertEqual(json.loads(path.read_text()), payload)
```

Para isso, `generate_payment_file()` precisa ser quebrado em
`_prepare_remessa_payload()` (puro, testável) + `_get_brcobranca_remessa()`
(I/O), o que já é uma melhoria por si só.

**Pagamentos (cnab_structure)**: o golden é o arquivo `.REM` byte a byte, com
data e sequência congeladas. `output_yaml()` já dá uma versão legível — o diff
de um YAML golden é ainda mais fácil de revisar do que o do arquivo posicional,
então vale manter os dois (`.rem` para garantia, `.yaml` para revisão).

**Efeito prático**: um PR "ajusta Santander" que mexeu em código comum aparece
como alteração nos goldens do Itaú, do BB e do Sicoob. O revisor vê na hora, sem
precisar conhecer os quatro manuais.

Complementos baratos e de alto retorno:

* Validação de *tiling* de posições: para cada combinação de grupos ativos, os
  campos precisam cobrir 1..N sem buraco e sem sobreposição. Pega o caso do BB
  acima e qualquer erro futuro de digitação de posição.
* Teste de arquitetura: falhar se `code_bc ==` / `code_bc in` aparecer fora de
  `models/banks/`. É o que transforma a regra em garantia.
* Matriz banco × formato × carteira gerada a partir do registry e publicada no
  README, em vez de mantida à mão.

## 5. Trilha B — adaptadores por banco (brcobranca)

Um `AbstractModel` por banco, um arquivo por banco, tudo continuando
sobrescrevível por terceiros via `_inherit` (importante para localizações
privadas):

```
l10n_br_account_payment_brcobranca/models/banks/
    __init__.py
    base.py            # l10n_br.cnab.bank  → comportamento FEBRABAN/padrão
    banco_brasil.py    # l10n_br.cnab.bank.001
    santander.py       # l10n_br.cnab.bank.033
    ...
```

```python
class CnabBank(models.AbstractModel):
    _name = "l10n_br.cnab.bank"
    _description = "Comportamento CNAB padrão (FEBRABAN)"

    _bank_code = None            # code_bc
    _brcobranca_name = None
    _formats = {}                # {"240": {...}, "400": {...}}

    # remessa (account.payment.order)
    def remessa_defaults(self, vals, cfg, order): ...
    def remessa_overrides(self, vals, cfg, order): ...
    # linha de pagamento (account.payment.line)
    def line_defaults(self, vals, cfg, line): ...
    def line_overrides(self, vals, cfg, line): ...
    # boleto (account.move.line)
    def boleto_values(self, vals, cfg, move_line): ...
    # retorno (parser)
    def return_own_number(self, linha_cnab): ...
    def return_registration_code(self): ...
    def return_state_from_occurrence(self, code): ...
    # validação
    def check_config(self, cfg): ...
```

Resolução única, sem `if`:

```python
def _cnab_bank(self, cnab_config):
    return self.env.get(f"l10n_br.cnab.bank.{cnab_config.bank_code_bc}") \
        or self.env["l10n_br.cnab.bank"]
```

Ordem de aplicação explícita (é o que hoje falta: os hooks rodam *antes* do
bloco genérico, então uma exceção de banco que precisa vir *depois* acaba
virando `if` no caminho comum):

```python
bank = self._cnab_bank(cfg)
vals = {}
bank.line_defaults(vals, cfg, self)      # antes
vals.update(self._prepare_line_febraban(cfg))   # base comum, sem if de banco
bank.line_overrides(vals, cfg, self)     # depois — aqui entram as exceções
```

Destino de cada `if` de hoje:

| Hoje | Vai para |
|---|---|
| `cod_desconto = "0"` p/ 085/104/033/136 e 001-240 | `line_overrides` de cada banco |
| `digito_conta_corrente` p/ 021/004 | `boleto_values` de banestes/inter |
| `byte_idt`/`posto` p/ 748/756 | `boleto_values` de sicredi/sicoob |
| `conta_corrente_dv` p/ 136 | `boleto_values` do unicred |
| `convenio` p/ 033 | `boleto_values` do santander |
| nosso número sem DV p/ 341 | `return_own_number` do itaú |
| ocorrência 51 p/ 004 | `return_state_from_occurrence` do nordeste |
| `allowed_registration_code` | `return_registration_code` de cada banco |
| carteira obrigatória p/ 341 | `check_config` do itaú |
| `DICT_BRCOBRANCA_BANK` | atributos `_brcobranca_name` / `_formats` de cada classe |

A **carteira** entra como dimensão dentro do adaptador do banco (o adaptador
recebe o `cnab_config` e decide), não como mais uma chave de dispatch global —
carteira só faz sentido dentro de um banco.

Ganho: para revisar um PR de banco novo basta olhar um arquivo; e é
estruturalmente impossível o PR alterar outro banco sem que o diff mostre.

## 6. Trilha A — herança de estrutura (cnab_structure)

Modelar no dado a mesma ideia: uma estrutura base FEBRABAN e bancos que só
declaram o delta.

```python
class CNABStructure(models.Model):
    _name = "l10n_br_cnab.structure"

    parent_id = fields.Many2one("l10n_br_cnab.structure", string="Herda de",
                                domain="[('is_template','=',True)]")
    is_template = fields.Boolean("Estrutura base")
```

```python
class CNABLine(models.Model):
    code = fields.Char(required=True,
        help="Chave estável da linha na estrutura: 'header_arquivo', "
             "'lote_pagamentos/segmento_a'. É por ela que a herança casa.")
    inherit_mode = fields.Selection(
        [("extend", "Estender"), ("replace", "Substituir"), ("remove", "Remover")],
        default="extend")

class CNABField(models.Model):
    inherit_mode = fields.Selection([...], default="extend")
    # chave de casamento: (line.code, start_pos, end_pos)
```

Resolução (mesma semântica de herança de view do Odoo, bem mais simples):

```python
def _resolve(self):
    """Retorna a estrutura efetiva: base + deltas, de trás para frente."""
    chain, node = [], self
    while node:
        chain.insert(0, node)
        node = node.parent_id
    resolved = {}
    for node in chain:
        for line in node.line_ids:
            for f in line.field_ids:
                key = (line.code, f.start_pos, f.end_pos)
                if f.inherit_mode == "remove":
                    resolved.pop(key, None)
                elif f.inherit_mode == "replace" or key not in resolved:
                    resolved[key] = f._vals()
                else:
                    resolved[key].update(f._vals(only_filled=True))
    return resolved
```

**Compilar, não resolver em runtime.** Recomendo materializar a estrutura
efetiva em registros (`compiled_from_id`, somente leitura) num botão
*"Compilar"* + hook de pós-instalação. Três motivos:

* `output()`, `check_structure()`, preview e o import de retorno continuam
  funcionando sem alteração;
* zero impacto de performance na geração do arquivo;
* a estrutura efetiva permanece **visível e auditável na interface** — em CNAB
  isso não é detalhe: quem valida com o banco precisa ver as 240 posições, não
  um delta.

Migração dos CSVs atuais: script que extrai a interseção funcional das 4
estruturas para `cnab_febraban_240_out` / `_in` e reescreve cada banco como
delta. Estimativa a partir dos números da seção 2.2: de 1.560 registros de campo
para ≈ 390 (base) + ≈ 100 por banco ≈ 790 — e, mais importante, o filler
231-240 passa a ser corrigido **em um lugar só**.

Cuidados conhecidos:

* Bancos que mudam *posição* (não só conteúdo) — coberto por `replace`/`remove`
  na chave `(line.code, start, end)`;
* Grupos condicionais precisam herdar junto (o `cnab.line.field.group` também
  ganha `code` + `inherit_mode`);
* A validação de tiling (Trilha C) tem que rodar **sobre a estrutura resolvida**,
  não sobre o delta.

## 7. Ordem sugerida

| # | Trilha | Esforço | Risco | Pré-requisito |
|---|---|---|---|---|
| 1 | C — goldens + tiling + teste de arquitetura | 2-3 dias | baixo | — |
| 2 | B — adaptadores no brcobranca | 3-5 dias | médio (refatoração pura, coberta pelos goldens) | 1 |
| 3 | A — herança de estrutura + migração dos CSVs | ~2 semanas | médio-alto (mexe em dado instalado) | 1 |
| 4 | Convergência: cobrança pelo `cnab_structure`, sem o serviço Ruby na remessa | grande | alto | 1, 2, 3 |

O item 4 é a consequência natural: o `cnab_structure` já suporta `inbound`
240/400/500. Uma vez que exista base FEBRABAN + herança + goldens, migrar a
remessa de cobrança para ele elimina a dependência do serviço externo na
geração (o BRCobrança continuaria só para o PDF do boleto). Não é pré-requisito
de nada — é onde isso desemboca se as três primeiras derem certo.

## 8. Checklist "banco novo" depois da refatoração

1. Criar `models/banks/<banco>.py` com `_bank_code`, `_formats` e só os hooks
   que o manual do banco exigir.
2. Criar a estrutura como filha de `cnab_febraban_240` com apenas os deltas.
3. Criar os goldens (`UPDATE_GOLDEN=1`) e conferir contra um arquivo homologado
   pelo banco.
4. Rodar a suíte: **nenhum golden de outro banco pode aparecer no diff.**
   Se aparecer, ou é bug da sua mudança, ou é correção de base — e aí precisa
   estar explícito na descrição do PR.
