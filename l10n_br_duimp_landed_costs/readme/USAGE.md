1.  Na DUIMP (aberta), clique em *Link Receipts*. Para cada item ainda
    sem recebimento aparece uma linha; quando há uma única linha de
    recebimento do mesmo produto com a quantidade que falta, ela vem
    sugerida. Confira, troque o que for preciso e confirme. Item sem
    linha escolhida continua pendente;
2.  valide os recebimentos, se ainda não estiverem validados;
3.  na aba *Customs Expenses*, escolha os documentos fiscais de entrada
    das despesas (NFS-e do despachante, armazenagem, CT-e). Cada linha
    precisa de um produto de custo e da linha de operação fiscal, como
    no `l10n_br_stock_landed_costs`;
4.  clique em *Create Landed Costs*: cada despesa ainda sem landed cost
    gera um, sobre os recebimentos da DUIMP, rateado por valor aduaneiro
    (ou pelo método escolhido no documento da despesa). Confira e
    valide cada landed cost.

O método *By Customs Value* também pode ser escolhido no documento de
uma despesa ou como método padrão do produto de custo, desde que os
recebimentos estejam ligados a itens de DUIMP.
