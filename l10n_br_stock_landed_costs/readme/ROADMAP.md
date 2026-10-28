- Na 16.0 este módulo foi escrito sobre a pilha de "custo líquido"
  (`l10n_br_fiscal.stock.price.mixin`, OCA #4965 a #4970), que não
  existe na 18.0. Aqui só a regra de creditabilidade necessária ao
  rateio foi trazida, dentro do próprio módulo e sem campos gravados:
  os recebimentos continuam valorados pelo preço padrão do Odoo, sem
  dedução de créditos. Quando a pilha for migrada, este módulo deve
  voltar a usar o `cost_unit` da linha e a opção
  `stock_valuation_via_stock_price` da empresa.
- Não há decisão manual da creditabilidade (motivo com base legal,
  `l10n_br_fiscal.creditability.reason`) nem a marca de origem da
  decisão: a creditabilidade é sempre derivada. Os CSTs que dão crédito
  ficam numa lista no módulo, e não no cadastro de CST.
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
  no custo.
- O lançamento do crédito na fatura do frete (conta de imposto a
  recuperar) é do módulo de contabilidade; aqui só o estoque é ajustado.
