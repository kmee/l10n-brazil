## Plano de Contas para Pequena Empresa (ITG 1000)

Este módulo entrega o plano de contas sugerido pelo Conselho Federal de
Contabilidade para a pequena empresa: o Anexo 7 da ITG 1000 de 15/12/2022
("Normas aplicáveis e modelos de plano de contas e demonstrações contábeis
para microentidade e pequena empresa"), que vale para os exercícios iniciados
a partir de 01/01/2023, junto com a NBC TG 1001 (pequena empresa) e a
NBC TG 1002 (microentidade).

A ITG 1000 de 2022 sucede a ITG 1000 de 2012 (Resolução CFC 1.418/2012,
revogada pela NBC TG 1002) e define as faixas pela receita bruta do exercício
anterior: microentidade até R$ 4.800.000,00; pequena empresa de
R$ 4.800.000,01 a R$ 78.000.000,00. A própria norma diz que o plano é
sugerido e que o contador pode adotar outro, conforme o detalhamento que
quiser nos registros (itens 20 e 22).

O plano serve às duas faixas. A microentidade (Anexo 11 da ITG 1000) usa o
mesmo esqueleto com menos contas: basta não usar, ou arquivar, as contas que
não se aplicam a ela (INSS patronal, IRPJ e CSLL, tributos retidos e a
recuperar, tributos diferidos, ágio e coligadas). Assim a empresa que cresce
não troca de plano: o Odoo carrega o plano uma vez por empresa, e as
demonstrações exigidas por cada norma são relatórios, montados a partir da
classificação das contas.

### O que a OCA acrescenta ao Anexo 7

- As contas de IBS, CBS e IS da reforma tributária (a recuperar, retidos na
  fonte, a pagar e sobre o faturamento).
- "3.1.2.01.09 IPI", dedução da receita, e "1.1.2.04.06 ISS Retido na Fonte",
  para os impostos que o Odoo lança e que o anexo não contempla.
- O anexo oficial repete alguns códigos (ativos fiscais diferidos,
  propriedades para investimento, tributos diferidos e partes relacionadas
  de longo prazo). Aqui eles recebem numeração própria: 1.2.1.02.xx,
  1.2.3.01.62 a 71, 2.2.2.02.xx e 2.2.3.01.xx.
- "Outras Despesas Antecipadas" é 1.1.4.01.99, dentro do grupo que existe
  (o anexo a numera 1.1.6.01.99, sem grupo 1.1.6).
- A classificação de cada conta para o Balanço, a DRE, a DFC e a DVA do
  módulo `l10n_br_mis_report`.

As contas padrão dos impostos (ICMS, IPI, PIS, COFINS, ISS, Simples Nacional,
retenções, IBS, CBS e IS) são as próprias contas do plano: a carga do plano
não cria conta ao lado delas.
