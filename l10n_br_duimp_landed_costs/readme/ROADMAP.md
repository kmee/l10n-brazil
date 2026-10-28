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
