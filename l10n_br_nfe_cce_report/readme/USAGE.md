Na NF-e, aba de eventos, grupo *Corrections*: o ícone de impressora da carta
passa a gerar este PDF. O relatório também fica no menu *Imprimir* do evento
fiscal.

Para testar o layout fora do Odoo, só com `fpdf2` e `lxml`:

    python l10n_br_nfe_cce_report/tests/test_cce_pdf.py /tmp/cce.pdf
