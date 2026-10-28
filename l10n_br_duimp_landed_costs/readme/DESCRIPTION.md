Uma importação gera despesas que chegam em documentos fiscais separados
da DUIMP: o despachante aduaneiro (NFS-e), a armazenagem, o frete
rodoviário do porto até o armazém (CT-e). Elas compõem o custo de
aquisição das mercadorias importadas (art. 301 do RIR/2018, CPC 16) e
precisam ser rateadas sobre os recebimentos daquela importação.

Este módulo liga a DUIMP (`l10n_br_duimp`) aos recebimentos e lança as
despesas aduaneiras como *landed cost* pelo `l10n_br_stock_landed_costs`
(a custo líquido quando a empresa marca *Landed Costs at Net Cost*):

- cada item da DUIMP é ligado à linha do recebimento que o trouxe. O
  sistema sugere a linha pelo produto e pela quantidade, e quem confirma
  é o usuário; item sem par fica pendente;
- as despesas aduaneiras são escolhidas na própria DUIMP, e um botão
  gera um landed cost por despesa sobre os recebimentos já ligados;
- o rateio ganha o método *por valor aduaneiro*: cada linha do
  recebimento pesa o valor aduaneiro do item da DUIMP que recebeu,
  proporcional à quantidade recebida. É a base que a própria DUIMP usa
  para ratear o AFRMM, a taxa do Siscomex e a capatazia.
