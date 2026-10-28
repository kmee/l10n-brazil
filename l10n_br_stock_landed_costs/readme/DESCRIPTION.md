Custos que chegam em documento fiscal separado da nota de compra (frete
em CT-e, despesas vinculadas) compõem o custo de aquisição do estoque
(art. 301 do RIR/2018, CPC 16) e são rateados sobre os recebimentos a
que se referem.

Este módulo gera um *landed cost* (`stock.landed.cost`) a partir de um
documento fiscal de entrada, com uma linha de custo por linha do
documento e rateio pelos métodos do Odoo (igual, quantidade, custo
atual, peso e volume).

O valor de cada linha é o custo líquido de aquisição calculado pelo
`l10n_br_fiscal.stock.price.mixin`, o mesmo que valora a entrada das
mercadorias: o imposto recuperável (o ICMS do CT-e, por exemplo) vira
crédito fiscal e não entra no estoque; o não recuperável fica no custo.
A creditabilidade segue os três portões da fundação (regime do
comprador, destino pelo CFOP, CST) e, no frete, o destino das
mercadorias dos recebimentos escolhidos: o frete de mercadoria para uso
e consumo ou para o ativo imobilizado não gera crédito.

Empresa que não valora o estoque pelo custo líquido (opção *Valuation
Via Stock Price* desligada) rateia o valor bruto do documento.

Para não contar duas vezes, não gere landed cost de frete que já veio
destacado (`freight_value`) na própria nota de compra: esse valor já
compõe o custo do recebimento.
