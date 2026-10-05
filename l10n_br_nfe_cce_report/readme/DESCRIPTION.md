Substitui a impressão da Carta de Correção Eletrônica (evento 110110) da
NF-e modelo 55 por um layout no molde do DANFE, com o logo da empresa: chave
de acesso, dados da NF-e e protocolo de autorização, emitente, destinatário
(inclusive idEstrangeiro), dados do evento, condição de uso e o texto da
correção.

Os dados saem dos XMLs que a localização já guarda: o XML autorizado da NF-e
(`authorization_file_id`) e os XMLs de envio e retorno do evento
(`file_request_id` e `file_response_id` do `l10n_br_fiscal.event`). Se algum
XML faltar, usa os campos gravados no Odoo.

Datas e horas saem no fuso registrado no próprio XML da SEFAZ (horário de
Brasília), sem conversão.
