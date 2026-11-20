#!/bin/zsh
# CI local do port bot: reproduz o job "test with Odoo" do CI da OCA
# (mesma imagem oca-ci, mesmo postgres, mesmos passos), limitado aos
# modulos tocados (INCLUDE) para ser rapido.
#
# uso: ci_local.sh <branch> <serie> <addons_csv>
# ex.: ci_local.sh 17.0-fw-l10n_br_hr 17.0 l10n_br_hr,l10n_br_hr_contract
set -eu
BRANCH="$1"; SERIE="$2"; ADDONS="$3"
REPO_GIT="${REPO_GIT:-/Users/mileo/Documents/kmee/projects/oca/l10n-brazil-code}"
# imagem do job "test with Odoo" lida do test.yml da propria branch (o Python
# muda por serie: py3.8 na 14.0, py3.10 na 16.0, ...); IMAGE no ambiente vence
IMAGE="${IMAGE:-$(git -C "$REPO_GIT" show "$BRANCH:.github/workflows/test.yml" 2>/dev/null \
  | grep -o "ghcr.io/oca/oca-ci/py[0-9.]*-odoo${SERIE}:latest" | head -1)}"
IMAGE="${IMAGE:-ghcr.io/oca/oca-ci/py3.10-odoo${SERIE}:latest}"
# postgres do servico do mesmo test.yml (12 na 18.0, 13 na 19.0, 16 na 20.0: o
# Odoo 20 nao sobe no 12); PG_IMAGE no ambiente vence
PG_IMAGE="${PG_IMAGE:-$(git -C "$REPO_GIT" show "$BRANCH:.github/workflows/test.yml" 2>/dev/null \
  | grep -o "image: postgres:[0-9.]*" | head -1 | cut -d' ' -f2)}"
PG_IMAGE="${PG_IMAGE:-postgres:12.0}"
RUN_ID="ocaci-$(echo $BRANCH | tr './' '--')"
# WORK unico por execucao: run anterior abortado deixa lixo root-owned do
# container que envenena o proximo (ex.: test-constraints.txt already exists).
# E fica DENTRO de $HOME: colima nao monta /tmp do host na VM (bind de /tmp
# vira dir vazio da VM e o container nao ve a arvore exportada).
WORK="${OCACI_WORK_BASE:-$HOME/.cache/ocaci}/${RUN_ID}-$$"
NET="${RUN_ID}-net"
PG="${RUN_ID}-pg"
BOLETO="${RUN_ID}-boleto"

cleanup() {
  # -v: o postgres declara VOLUME e sem ele o volume anonimo fica para tras
  docker rm -fv "$PG" >/dev/null 2>&1 || true
  docker rm -fv "$BOLETO" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
  rm -rf "$WORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT
# limpa restos de runs anteriores ANTES de exportar a arvore: cleanup tambem
# apaga o WORK, entao nunca chamar depois do archive (bug ja pago: container
# montava diretorio vazio e o manifestoo nao achava addon nenhum)
cleanup

echo "== exporta arvore da branch $BRANCH =="
mkdir -p "$WORK"
git -C "$REPO_GIT" archive "$BRANCH" | tar -x -C "$WORK"

# o test.yml da 18.0 liga OCA_ENABLE_CHECKLOG_ODOO: sem repassar, oca_checklog_odoo
# vira `cat` e WARNING no log (ex.: "cannot be precomputed") passa verde aqui e
# reprova no CI da OCA (pago no #5151 em 2026-10-01)
CHECKLOG=""
if grep -q 'OCA_ENABLE_CHECKLOG_ODOO: "1"' "$WORK/.github/workflows/test.yml" 2>/dev/null; then
  CHECKLOG=1
fi
echo "== checklog: ${CHECKLOG:-desligado (como no test.yml da serie)} | postgres: $PG_IMAGE =="

echo "== sobe postgres =="
docker network create "$NET" >/dev/null
docker run -d --rm --name "$PG" --network "$NET" --network-alias postgres \
  -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo -e POSTGRES_DB=odoo \
  "$PG_IMAGE" >/dev/null
# servico que o test.yml da OCA sobe para o l10n_br_account_payment_brcobranca;
# sem ele os 17 testes do modulo dao "BRCobranca API URL is not configured".
# So sobe quando um modulo de boleto esta entre os testados (imagem amd64, lenta)
if [[ "$ADDONS" == *brcobranca* ]]; then
  docker run -d --rm --name "$BOLETO" --network "$NET" --network-alias boleto_cnab_api \
    --platform linux/amd64 ghcr.io/akretion/boleto_cnab_api:latest >/dev/null
fi
sleep 5

echo "== roda oca-ci ($IMAGE) INCLUDE=$ADDONS =="
# imagem oca-ci e amd64-only: no Mac ARM roda via Rosetta (colima: habilitar vz+rosetta)
docker run --rm --network "$NET" --platform linux/amd64 \
  -e PGHOST=postgres -e PGUSER=odoo -e PGPASSWORD=odoo -e PGDATABASE=odoo \
  -e INCLUDE="$ADDONS" -e OCA_ENABLE_CHECKLOG_ODOO="$CHECKLOG" -e BRCOBRANCA_API_URL=http://boleto_cnab_api:9292 \
  -e PERMITIR_ZERO_TESTES="${PERMITIR_ZERO_TESTES:-}" \
  -v "$WORK":/mnt/repo -w /mnt/repo \
  "$IMAGE" bash -ec '
    set -o pipefail
    oca_install_addons
    manifestoo -d . check-licenses
    manifestoo -d . check-dev-status --default-dev-status=Beta
    # oca_init_test_database quebra com INCLUDE: chama manifestoo list-depends
    # sem addons-dir e o default (import odoo) nao enxerga /mnt/repo. Fazemos o
    # mesmo init com o manifestoo apontado para o diretorio.
    DEPS=$(manifestoo -d . --select-include "$INCLUDE" list-depends --separator=,)
    [ -z "$DEPS" ] && DEPS=base
    oca_wait_for_postgres
    unbuffer $(which odoo) -d "$PGDATABASE" -i "$DEPS" --http-interface=127.0.0.1 --stop-after-init | oca_checklog_odoo
    oca_run_tests 2>&1 | tee /tmp/oca_run_tests.log
    # zero testes executados e falha, mesmo com exit 0 (regra da frente UAE, licao
    # ci-verde-pode-significar-nada-rodou): modulo sem manifest ou INCLUDE errado
    # passa verde sem rodar nada. Modulo so de dados: PERMITIR_ZERO_TESTES=1
    RESUMO=$(grep -Eo "[0-9]+ failed, [0-9]+ error\(s\) of [0-9]+ tests" /tmp/oca_run_tests.log | tail -1 || true)
    # 14.0 nao tem essa linha: o runner do unittest imprime "Ran N tests" por modulo
    [ -z "$RESUMO" ] && grep -Eq "Ran [1-9][0-9]* tests?" /tmp/oca_run_tests.log && RESUMO="Ran N tests (14.0)"
    echo "== resumo dos testes: ${RESUMO:-linha de resumo nao encontrada} =="
    if [ -z "$PERMITIR_ZERO_TESTES" ] && { [ -z "$RESUMO" ] || [[ "$RESUMO" == *" of 0 tests" ]]; }; then
      echo "== ZERO TESTES EXECUTADOS: o CI verde nao provaria nada (PERMITIR_ZERO_TESTES=1 para modulo sem testes) =="
      exit 1
    fi
  '
echo "== CI LOCAL VERDE: $BRANCH ($ADDONS) =="
