- Grupo `comExt`: a moeda vai com o código do BACEN, como pede o XSD, mas a
  NFS-e autorizada mostra o código ISO, USD; confirmar na primeira emissão.
  A exportação faturada em reais sai sem o grupo, e a movimentação temporária
  de bens e o envio ao MDIC ficam fixos em não e em não enviar.
- Confirmar a substituição (`SubstituirNfse`) no webservice: na homologação de
  Guarulhos o GissOnline aceita o XML (schema e as três assinaturas), mas responde
  A01 e "Função desabilitada"; falta a prefeitura habilitar a função para o
  contribuinte.
- Ler de volta os valores de IBS/CBS calculados pela prefeitura no retorno
  (`IBSCBSTotal`).
- Um RPS por lote: o webservice aceita até 50.
