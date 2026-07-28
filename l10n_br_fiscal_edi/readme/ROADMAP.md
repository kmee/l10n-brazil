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
