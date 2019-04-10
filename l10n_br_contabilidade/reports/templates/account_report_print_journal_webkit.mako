## -*- coding: utf-8 -*-
<!DOCTYPE html SYSTEM "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <style type="text/css">
            .overflow_ellipsis {
                text-overflow: ellipsis;
                overflow: hidden;
                white-space: nowrap;
            }
            ${css}
        </style>
    </head>
    <body>
        <%!
        def amount(text):
            return text.replace('-', '&#8209;')  # replace by a non-breaking hyphen (it will not word-wrap between hyphen and numbers)
        %>

        <%setLang(user.lang)%>

        <div class="act_as_table data_table" style="width: 100%;">
            <div class="act_as_row labels">
                <div class="act_as_cell">${_('Chart of Account')}</div>
                <div class="act_as_cell">${_('Fiscal Year')}</div>
                <div class="act_as_cell">
                    %if filter_form(data) == 'filter_date':
                        ${_('Dates Filter')}
                    %else:
                        ${_('Periods Filter')}
                    %endif
                </div>
                <div class="act_as_cell">${_('Journal Filter')}</div>
                <div class="act_as_cell">${_('Target Moves')}</div>
            </div>
            <div class="act_as_row">
                <div class="act_as_cell">${ chart_account.name }</div>
                <div class="act_as_cell">${ fiscalyear.name if fiscalyear else '-' }</div>
                <div class="act_as_cell">
                    ${_('From:')}
                    %if filter_form(data) == 'filter_date':
                        ${formatLang(start_date, date=True) if start_date else u'' }
                    %else:
                        ${start_period.name if start_period else u''}
                    %endif
                    ${_('To:')}
                    %if filter_form(data) == 'filter_date':
                        ${ formatLang(stop_date, date=True) if stop_date else u'' }
                    %else:
                        ${stop_period.name if stop_period else u'' }
                    %endif
                </div>
                <div class="act_as_cell">
                    %if journals(data):
                        ${', '.join([journal.name for journal in journals(data)])}
                    %else:
                        ${_('All')}
                    %endif

                </div>
                <div class="act_as_cell">${ display_target_move(data) }</div>
            </div>
        </div>

        <%
        account_total_debit = 0.0
        account_total_credit = 0.0
        account_total_currency = 0.0
        %>

        <!-- we use div with css instead of table for tabular data because
        div do not cut rows at half at page breaks -->
        <div class="act_as_table list_table" style="margin-top: 5px;">
            <div class="act_as_thead">
                <div class="act_as_row labels">
                    ## date
                    <div class="act_as_cell first_column" style="width: 60px;">${_('Date')}</div>
                    ## move
                    <div class="act_as_cell" style="width: 150px;">${_('Entry')}</div>
                    ## account code
                    <div class="act_as_cell" style="width: 95px;">${_('Account')}</div>
                    ## journal
                    <div class="act_as_cell overflow_ellipsis" style="width: 100px;">${_('Journal')}</div>
                    ## label
                    <div class="act_as_cell" style="width: 450px;">${_('Label')}</div>
                    ## debit
                    <div class="act_as_cell amount" style="width: 125px;">${_('Debit')}</div>
                    ## credit
                    <div class="act_as_cell amount" style="width: 125px;">${_('Credit')}</div>
                </div>
            </div>
            %for move in moves:
                <div class="act_as_tbody">
                %for line in move.line_id:

                    <%
                    account_total_debit += line.debit or 0.0
                    account_total_credit += line.credit or 0.0
                    %>
                    <div class="act_as_row lines">
                        ## date
                        <div class="act_as_cell first_column" style="width: 60px;">${formatLang(move.date, date=True)}</div>
                        ## move
                        <div class="act_as_cell" style="width: 150px;">${move.name}</div>
                        ## account code
                        <div class="act_as_cell" style="width: 95px;">${line.account_id.code}</div>
                        ## journal
                        <div class="act_as_cell overflow_ellipsis" style="width: 100px;">${line.journal_id.name}</div>
                        ## label
                        <div class="act_as_cell overflow_ellipsis" style="width: 450px;">${line.name}</div>
                        ## debit
                        <div class="act_as_cell amount" style="width: 125px;">${formatLang(line.debit) if line.debit else ''}</div>
                        ## credit
                        <div class="act_as_cell amount" style="width: 125px;">${formatLang(line.credit) if line.credit else ''}</div>
                    </div>

                %endfor
                </div>
            %endfor
            <div class="act_as_row lines labels">
                ## date
                <div class="act_as_cell first_column" style="width: 60px;"></div>
                ## move
                <div class="act_as_cell" style="width: 150px;"></div>
                ## account code
                <div class="act_as_cell" style="width: 95px;"></div>
                ## journal
                <div class="act_as_cell overflow_ellipsis" style="width: 100px;"></div>
                ## label
                <div class="act_as_cell overflow_ellipsis" style="width: 450px;"></div>
                ## debit
                <div class="act_as_cell amount">${formatLang(account_total_debit) | amount }</div>
                ## credit
                <div class="act_as_cell amount">${formatLang(account_total_credit) | amount }</div>
            </div>
        </div>
    </body>
</html>
