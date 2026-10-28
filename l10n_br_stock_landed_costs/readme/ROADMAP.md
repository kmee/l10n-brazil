- A creditabilidade do ICMS do frete (CT-e) ainda não tem regra fiscal
  própria na localização. O módulo usa a regra das mercadorias e é
  conservador: o crédito só é tomado quando os três portões permitem e
  nenhum recebimento escolhido veta (uso e consumo, ativo imobilizado ou
  recebimento sem CFOP). Na dúvida, o imposto fica no custo.
- O CT-e importado pelo `l10n_br_cte` não traz produto nem linha de
  operação fiscal: é preciso preenchê-los antes de gerar o landed cost.
  Sem a linha de operação o valor bruto é rateado.
- O crédito de ICMS do ativo imobilizado em 48 avos (CIAP) e o crédito
  parcial de PIS e COFINS não são tratados: nesses casos o imposto fica
  no custo, como na entrada das mercadorias.
- O lançamento do crédito na fatura do frete (conta de imposto a
  recuperar) é do módulo de contabilidade; aqui só o estoque é ajustado.
