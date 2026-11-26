Leva a referência do cliente (`client_order_ref`) e o pedido de venda ao
documento fiscal e à fatura, inclusive quando a fatura nasce da remessa
(`l10n_br_sale_stock`). A referência por linha do módulo
`sale_order_line_client_order_ref` também entra no documento.

O campo **Referência do cliente** do documento fiscal pode ser usado nos
comentários fiscais (`doc.client_order_ref`) para imprimir a referência nas
informações complementares da NF-e.
