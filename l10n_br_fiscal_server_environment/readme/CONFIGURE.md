No diretório do ambiente em que o servidor roda (`dev`, `hml`, `prod`...,
conforme `RUNNING_ENV`), dentro do módulo de arquivos de ambiente do
`server_environment`, crie um arquivo `.conf` com a seção `[res_company]`
para valer para todas as empresas e, se precisar, seções
`[res_company.<nome da empresa>]` para empresas específicas. Os valores são
`1` (produção) e `2` (homologação):

    [res_company]
    nfe_environment = 2
    nfse_environment = 2

    [res_company.Metalúrgica Santa Rita Ltda]
    nfe_environment = 1

Chave ausente no arquivo: a empresa usa o valor gravado no cadastro e o
campo continua editável. Chave presente: vale o valor do arquivo e o campo
fica somente leitura.
