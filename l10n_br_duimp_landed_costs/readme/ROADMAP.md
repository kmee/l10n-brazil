- O rateio por valor aduaneiro exige que toda linha dos recebimentos
  escolhidos esteja ligada a um item de DUIMP. Recebimento que mistura
  mercadoria importada e nacional é recusado; separe os recebimentos.
- O assistente só mostra os itens pendentes e ainda não há tela para
  desfazer uma ligação confirmada.
- O valor do recebimento das mercadorias continua vindo do próprio
  recebimento (pedido de compra ou documento de entrada); este módulo não
  copia para ele os tributos e despesas da DUIMP.
- Capatazia e armazenagem não vêm em API oficial: entram pelo documento
  do terceiro (NFS-e do recinto, fatura do armador) como despesa
  aduaneira. Nesse caso deixe a capatazia da DUIMP em zero, porque o
  valor informado nela vai para o *other_value* da nota de importação e
  seria contado duas vezes.
- Na 16.0 este módulo foi escrito sobre a pilha de "custo líquido"
  (`l10n_br_fiscal.stock.price.mixin`, OCA #4965 a #4970), que não
  existe na 18.0. O módulo não usa nada dela diretamente: as despesas
  são lançadas pelo `l10n_br_stock_landed_costs` 18.0, que só as rateia
  a custo líquido (descontando os créditos de ICMS, IPI, PIS e COFINS)
  quando a empresa marca *landed_cost_net_cost*. Os recebimentos das
  mercadorias continuam valorados pelo preço padrão do Odoo, sem
  dedução dos créditos da importação. Quando a pilha for migrada, o
  teste de ponta a ponta deve voltar a conferir a valoração dos
  recebimentos pelo `cost_unit`.
