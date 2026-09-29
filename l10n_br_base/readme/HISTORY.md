## 20.0.1.0.0 (2026)

O Odoo 20 removeu o modelo `res.bank` e levou o `res.partner.bank` para o
`base`, com o nome e o BIC do banco como campos de texto na própria conta.
A tabela de bancos brasileiros (código COMPE, ISPB, membro da COMPE)
passou para o modelo `l10n_br_base.bank`, ligado à conta bancária pelo
campo `l10n_br_bank_id`, que preenche o nome e o BIC do banco da conta.

O Odoo 20 também passou a calcular o campo "É uma empresa" a partir do
VAT. Na localização brasileira, parceiro com CPF é pessoa física e
parceiro com CNPJ é empresa.

## 12.0.1.0.0 (2019)

A partir da versão 12.0 foi extraído o pacote de validações cadastrais
`erpbrasil.base` no intuito de minimizar o código que depende de uma
versão especifica do Odoo e para desenvolver sinergias com outras
comunidades de código aberto.

## 11.0 (unreleased)

Devido ao atraso com a versão 11.0 foi decido de pular a versão 11.0 e
trabalhar direitamente para a versão 12.0.

## 10.0.1.0.0 (2017)

Devido ao trabalho enorme com a reescritura do módulo de contabilidade
na versão 9 e a problemas pessoas de um dos autores, essa versão atrasou
um pouco para sair.

## 9.0.1.0.0 (2015)

## 8.0.1.0.0 (2014)

## 7.0.1.0.0 (2013)

Mudança do Launchpad para Github. Mudança importante com a unificação
das tabelas de parceiros e endereços.

## 6.1.1.0.0 (2012)

## 6.0.1.0.0 (2011)

## 5.0.1.0.0 (2009)

Este módulo foi criado na versão 5.0 do Odoo então chamado OpenERP. Era
inicialmente hospedado na plataforma Launchpad.
