# Goldens do arquivo CNAB gerado

Cada arquivo aqui é a remessa posicional gerada para uma estrutura de banco,
congelada. Diferente do módulo de cobrança, aqui os bytes são gerados pelo
próprio Odoo, então o golden é o arquivo inteiro.

Nomeação: `<código do banco>_<nome>_<formato>.rem`, ex.: `341_itau_240.rem`.

## Semear ou atualizar

```bash
UPDATE_GOLDEN=1 odoo --test-enable --stop-after-init \
    -d <base> -u l10n_br_cnab_structure
```

O horário de geração é congelado no teste (`FrozenTime`), assim como o nome da
ordem, o nome das linhas e as datas — sem isso o arquivo mudaria a cada
execução. Ao semear, cada arquivo é gerado duas vezes e as duas execuções
precisam ser idênticas; se não forem, o teste falha apontando a linha e a
posição que variou, em vez de gravar um golden instável.

## Ao revisar um PR

Em arquivo posicional o diff é literalmente a linha e a coluna que mudaram.
Se o PR se propôs a mexer em um banco e o golden de outro apareceu no diff,
a mudança é comum a todos e precisa estar explícita na descrição.
