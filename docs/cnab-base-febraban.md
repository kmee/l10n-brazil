# Refatoração do framework CNAB: base FEBRABAN + bancos por cima

> RFC da refatoração. A **trilha C** (seção 4) está implementada; as trilhas
> A e B ainda são proposta, para discussão antes de mexer.

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
* BB, segmento A: o campo `DV CONTA` (42-42) existia duas vezes — uma sem grupo
  e outra em `group_1_bb`. Só não gerava linha de 241 caracteres porque
  `CnabLine.sorted_values()` monta um `dict` por `ref_name` e **silenciosamente
  deduplica**. Se os dois campos tivessem nomes diferentes, o arquivo sairia
  errado sem nenhum erro. *Corrigido na trilha C, junto com a validação que o
  detectou.*
* `CNABLine.check_line()` validava apenas que o primeiro campo começa em 1 e o
  último termina em 240 — **não validava buraco nem sobreposição no meio**.
  *Corrigido na trilha C.*

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

## 4. Trilha C — golden tests por banco (implementada)

Sem isso, as trilhas A e B são apostas. Com isso, viram refatorações
verificáveis. O que foi entregue:

**Infraestrutura** — `l10n_br_account_payment_order/tests/golden.py`
(`GoldenMixin`). Congela a saída de um caso em disco e compara nas execuções
seguintes. Ao semear com `UPDATE_GOLDEN=1`, cada caso é gerado **duas vezes** e
as duas execuções precisam bater: é assim que se prova que o golden é
determinístico em vez de descobrir depois, por falha intermitente, que sobrou
uma data de "hoje" ou uma sequência dentro dele. Quando o golden ainda não
existe, o teste é pulado com a instrução de como gerá-lo.

**Cobrança (brcobranca)** — os bytes são gerados pelo Ruby, mas o que o Odoo
controla, e onde estão todas as particularidades de banco e de carteira, é o
payload enviado à API. Então `generate_payment_file()` foi quebrado em
`_prepare_remessa_payload()` (puro, sem I/O) + `_get_brcobranca_remessa()`
(I/O), e o golden é o payload. Resultado: `tests/test_golden_remessa.py` cobre
11 casos (BB 240/400, Nordeste 400, Santander 240/400, Ailos 240, Caixa 240,
Unicred 400, Bradesco 400, Itaú 400, Sicredi 240) e roda **sem o serviço
externo**, ao contrário dos testes existentes, que são pulados com
`CI_NO_BRCOBRANCA`.

Os valores que variam são fixados no teste — e não de forma arbitrária: o
nosso número com 8 dígitos exercita o corte para 7 + DV do Santander 400 e o
número do documento com 11 dígitos exercita o corte para 10 do Unicred. As
particularidades de banco ficam dentro do golden, não fora dele.

**Pagamentos (cnab_structure)** — o golden é o arquivo `.REM` inteiro, byte a
byte, para as quatro estruturas (Itaú, BB, Santander e Sicoob 240). O horário
de geração é congelado substituindo o `time` do `safe_eval` dos campos; nome da
ordem, nome das linhas e datas são fixados.

Em arquivo posicional, o diff de um golden é literalmente a linha e a coluna
que mudaram — e é assim que a falha é reportada ("primeira divergência na
linha 3, posição 154"), em vez de um diff de texto corrido de 240 colunas.

**Cobertura de posições** — `l10n_br_cnab_structure/tests/test_data_layout.py`
valida as estruturas entregues sem precisar de banco de dados, e
`CNABLine._check_field_positions()` valida as estruturas criadas pelo usuário.
As regras, derivadas de como `CNABLine.output()` monta a linha:

* nenhum campo de grupo condicional pode disputar posição com um campo sem
  grupo, que é sempre emitido;
* a união de todos os campos precisa cobrir a linha inteira, sem buraco;
* dois campos com o mesmo `ref_name` emitidos juntos são proibidos, porque um
  sobrescreve o outro em silêncio.

Grupos diferentes *podem* definir as mesmas posições — são variantes
mutuamente exclusivas, como "conta no mesmo banco" e "conta em outro banco".

A validação já encontrou e corrigiu um caso real: no segmento A do Banco do
Brasil o campo `DV CONTA` (42-42) estava definido duas vezes, uma sem grupo e
outra em "Conta Corrente - Mesmo Banco". A linha só não saía com 241
caracteres porque `sorted_values()` monta um `dict` por `ref_name` e
deduplicava por acidente — bastaria um dos dois ter nome ligeiramente
diferente para o arquivo sair errado sem nenhum erro.

**Catraca de `if` de banco** —
`l10n_br_account_payment_brcobranca/tests/test_no_bank_conditionals.py`
inventaria as 15 ramificações por banco que existem hoje no caminho comum
(4 arquivos). Uma nova falha o teste; uma removida também falha, pedindo que o
inventário seja atualizado. Assim o número só cai, o inventário nunca fica
desatualizado e o progresso da trilha B fica visível.

**Pendente**: semear os goldens. Isso precisa de um ambiente com Odoo e banco
de dados, e cada arquivo deve ser conferido contra uma remessa homologada pelo
banco antes de ser commitado — um golden errado congelado vira uma verdade
errada. Enquanto não forem semeados, os testes golden são pulados com a
instrução; as demais travas desta trilha já valem.

Complemento ainda não feito: a matriz banco × formato × carteira gerada a
partir do registry, em vez de mantida à mão no README. Ela depende do registry
da trilha B.

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
| 1 | C — goldens + tiling + catraca | ~~2-3 dias~~ **feito** (falta semear os goldens) | baixo | — |
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
