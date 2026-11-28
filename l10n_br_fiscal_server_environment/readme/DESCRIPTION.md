Controla o ambiente de NF-e e de NFS-e (produção ou homologação) de cada
empresa pelo arquivo de ambiente do servidor (`server_environment`), em vez
do cadastro da empresa.

Assim, uma base restaurada em desenvolvimento ou homologação não transmite
documentos em produção por engano: o arquivo do ambiente em que o servidor
roda decide o ambiente fiscal, e o campo na tela da empresa fica somente
leitura enquanto o arquivo define o valor.
