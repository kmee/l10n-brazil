# kmee-ci

Branch orfa do fork `kmee/l10n-brazil`, sem codigo do l10n-brazil. Guarda so o
workflow do runner self-hosted da KMEE (`.github/workflows/kmee-ci.yml`) e o
`ci_local.sh`, que reproduz o job "test with Odoo" do CI da OCA (mesma imagem
oca-ci, mesmo postgres) so nos addons pedidos.

E a branch padrao do fork porque o `workflow_dispatch` exige o workflow na branch
padrao. Nao abrir PR a partir dela e nao mesclar nada nela vindo do l10n-brazil.

Disparo (so quem tem escrita no fork):

```
gh workflow run kmee-ci.yml -R kmee/l10n-brazil --ref kmee-ci \
  -f branch=<branch do fork> -f serie=16.0 -f addons=l10n_br_fiscal
```

O runner roda numa maquina isolada da rede interna e so atende a label
`kmee-l10n-br`. Nao ha gatilho de `push` nem de `pull_request` aqui.
