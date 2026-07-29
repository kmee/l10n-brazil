# Copyright (C) 2025  Renato Lima - Akretion <renato.lima@akretion.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    SITUACAO_EDOC_AUTORIZADA,
    SITUACAO_EDOC_DENEGADA,
    SITUACAO_EDOC_ENVIADA,
    SITUACAO_EDOC_REJEITADA,
)

# Aliases of the values declared by l10n_br_fiscal: the states of an
# electronic document belong to the base module (see the comment on
# DOCUMENT_STATES there), this module only owns the transitions between them.
DOCUMENT_STATE_SENDING = SITUACAO_EDOC_ENVIADA
DOCUMENT_STATE_AUTHORIZED = SITUACAO_EDOC_AUTORIZADA
DOCUMENT_STATE_REJECTED = SITUACAO_EDOC_REJEITADA
DOCUMENT_STATE_DENIED = SITUACAO_EDOC_DENEGADA
