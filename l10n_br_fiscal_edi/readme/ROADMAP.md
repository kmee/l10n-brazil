Camada de compatibilidade da API legada
---------------------------------------

O código do `document_workflow.py` é uma espécie de tradução em código do
"workflow de state machine" que tinha sido customizado para a NFe na versão
8.0 mas que teve que ser re-escrito quando o engine de workflow foi removido
na versão 10.0. Ele agora é a camada de compatibilidade da máquina de estados.

O mixin `l10n_br_fiscal.document.workflow`
(`models/document_workflow.py`) mantém funcionando a interface do workflow
anterior à máquina de estados (`_change_state`, `_avaliable_transition`,
`_exec_before_SITUACAO_EDOC_*` / `_exec_after_SITUACAO_EDOC_*`,
`_before_change_state` / `_after_change_state`, `_document_confirm`,
`_document_send` etc.), usada pelos módulos de transmissão deste repositório,
pelos provedores municipais de NFS-e e por módulos de terceiros.

A máquina de estados é o motor: ela é a fonte única de verdade das transições
permitidas (`get_state_machine_config()`) e `_change_state()` é o único ponto
de escrita de `state_edoc`. Tanto os gatilhos novos (`_trigger_fsm`) quanto os
botões legados passam por ele, de modo que os callbacks novos
(`_before_document_*` / `_after_document_*`) e os hooks legados são chamados
no mesmo ponto do fluxo.

A migração para a API nova é incremental, um módulo por vez. A camada de
compatibilidade só será removida quando não houver mais nenhum consumidor da
API legada, com aviso prévio à comunidade e `DeprecationWarning` ativo por
pelo menos um ciclo de releases.

Bloqueante para remover a camada: o veto por retorno
------------------------------------------------------

A API legada tem um recurso que a API nova ainda não tem: um
`_exec_before_SITUACAO_EDOC_*` que devolve um valor falso **veta** a
transição sem levantar erro. Isso é usado em produção, por exemplo pelo
`l10n_br_nfse_focus`, que assim impede que um documento de outro provedor
seja cancelado pelo caminho dele.

Os callbacks novos (`_before_document_*`) não têm esse poder: o retorno deles
é ignorado, porque um callback `before` da biblioteca `transitions` não
aborta a transição (só uma `condition` aborta). Enquanto a API nova não
oferecer equivalente, remover a camada de compatibilidade tira do ecossistema
a capacidade de recusar uma transição em silêncio, e o cancelamento de NFS-e
municipal quebraria sem erro visível.

Portanto, antes de remover a camada:

1. dar às transições da máquina um mecanismo de recusa explícito, via
   `conditions` declaradas em `get_state_machine_config()`;
2. migrar os consumidores do veto por retorno para esse mecanismo;
3. só então emitir o `DeprecationWarning` e marcar a data de remoção.
