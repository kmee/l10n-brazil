# Goldens da remessa (payload BRCobrança)

Cada arquivo aqui é o payload JSON que o Odoo envia ao BRCobrança para um
banco e um formato CNAB, congelado. É a rede de segurança contra o problema
clássico deste módulo: um ajuste feito para um banco alterar, sem ninguém
perceber, o que é enviado para outro.

Nomeação: `<código do banco>_<nome>_<formato>.json`, ex.: `033_santander_240.json`.

## Semear ou atualizar

```bash
UPDATE_GOLDEN=1 odoo --test-enable --stop-after-init \
    -d <base> -u l10n_br_account_payment_brcobranca
```

Ao semear, cada payload é gerado duas vezes e as duas execuções precisam ser
idênticas — é assim que se garante que não sobrou data de "hoje" nem sequência
no golden. Enquanto o arquivo não existe, o teste correspondente é pulado com
a instrução de como gerá-lo.

## Ao revisar um PR

* O PR mexeu só no banco X e só o golden do banco X mudou → ok.
* O PR mexeu no banco X e mudou o golden de outro banco → ou é bug, ou é uma
  mudança de comportamento comum e precisa estar dita na descrição do PR.
* O PR adiciona um banco → deve adicionar o golden dele, conferido contra um
  arquivo homologado pelo banco.
