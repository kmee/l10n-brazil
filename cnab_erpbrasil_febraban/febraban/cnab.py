# © 2012 KMEE INFORMATICA LTDA
#   @author Luis Felipe Mileo <mileo@kmee.com.br>
#   @author Daniel Sadamo <daniel.sadamo@kmee.com.br>
#   @author Fernando Marcato <fernando.marcato@kmee.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
import base64
import codecs
import re
from unidecode import unidecode
from datetime import datetime

_logger = logging.getLogger(__name__)

try:
    from febraban.cnab240.itau.sispag import \
        Transfer, DasPayment, IssPayment, UtilityPayment, File
    from febraban.cnab240.itau.charge import Slip, SlipParser, File as SlipFile
    from febraban.cnab240.itau.sispag.file.lot import Lot
    from febraban.cnab240.libs.barCode import LineNumberO
    from febraban.cnab240.user import User, UserAddress, UserBank
except ImportError as err:
    _logger.debug = (err)


class Cnab(object):

    def __init__(self):
        self.arquivo = False
        self.cnab_type = False

    @staticmethod
    def _prepare_user(partner_id, company_partner_bank_id=None):
        user_bank = None
        if company_partner_bank_id:
            user_bank = UserBank(
                bankId=company_partner_bank_id.bank_id.code_bc or False,
                branchCode=company_partner_bank_id.bra_number or False,
                accountNumber=company_partner_bank_id.acc_number or False,
                accountVerifier=company_partner_bank_id.acc_number_dig or False,
                bankName=unidecode(
                    re.sub(
                        r'[\W_]+', ' ',
                        company_partner_bank_id.bank_id.name)) or False,
            )

        return User(
            name=partner_id.legal_name.upper(),
            identifier=partner_id.cnpj_cpf.replace(
                '.', '').replace('/', '').replace('-', ''),
            bank=user_bank,
            address=UserAddress(
                streetLine1=(partner_id.street + ' ' +
                             (partner_id.street_number
                              or '')).upper(),
                city=unidecode(partner_id.city_id.name).upper(),
                stateCode=partner_id.state_id.code,
                zipCode=partner_id.zip.replace('-', '')
            )
        )

    @staticmethod
    def _prepare_charge(order):
        bank_id = order.company_partner_bank_id
        partner_id = order.company_id.partner_id

        sender = Cnab._prepare_user(partner_id, bank_id)

        file = SlipFile()
        file.setSender(sender)
        file.setIssueDate(datetime.now())

        for line in order.bank_line_ids:
            receiver = Cnab._prepare_user(line.partner_id)

            slip = Slip()
            slip.setSender(sender)
            slip.setAmountInCents(str(int(line.amount_currency * 100)))
            slip.setPayer(receiver)
            slip.setIssueDate(datetime.now())
            slip.setExpirationDate(datetime.now())
            slip.setBankIdentifier(
                identifier="1",
                branch=sender.bank.branchCode,
                accountNumber=sender.bank.accountNumber,
                wallet=order.payment_mode_id.boleto_wallet
            )
            slip.setIdentifier(order.name)
            slip.setFineAndInterest(datetime=datetime.now(), fine="0",
                                    interest="0")
            slip.setOverdueLimit("3")
            file.add(register=slip)

        return file.toString().encode()

    @staticmethod
    def _prepare_sispag(order):
        bank_id = order.company_partner_bank_id.bank_id
        partner_id = order.company_id.partner_id

        sender = Cnab._prepare_user(partner_id, bank_id)

        bank_line_obj = order.env['bank.payment.line']
        option_obj = order.env['l10n_br.cnab.option']

        file = File()
        file.setSender(sender)

        for group in bank_line_obj.read_group(
            [('id', 'in', order.bank_line_ids.ids)],
            [], ['release_form_id', 'service_type_id'], lazy=False
        ):
            lot = Lot()
            sender.name = order.company_id.legal_name.upper()
            lot.setSender(sender)
            lot.setHeaderLotType(
                kind=option_obj.browse(group['service_type_id'][0]).code,
                method=option_obj.browse(group['release_form_id'][0]).code,
            )

            for line in bank_line_obj.search(group['__domain']):
                receiver = Cnab._prepare_user(line.partner_id, line.partner_bank_id)

                if line.release_form_id.code == "41":
                    payment = Transfer()
                    payment.setSender(sender)
                    payment.setReceiver(receiver)
                    payment.setAmountInCents(str(int(line.amount_currency * 100)))
                    payment.setScheduleDate(line.date.strftime('%d%m%Y'))
                    payment.setInfo(
                        reason="10"  # Crédito em Conta Corrente
                    )
                    payment.setIdentifier("ID%s" % line.own_number)
                elif line.release_form_id.code == "91":
                    payment = DasPayment()
                    payment.setPayment(
                        sender=sender,
                        scheduleDate=line.date.strftime('%d%m%Y'),
                        identifier="ID%s" % line.own_number,
                        lineNumber=LineNumberO(line.communication)
                    )
                elif line.release_form_id.code == "19":
                    payment = IssPayment()
                    payment.setPayment(
                        sender=sender,
                        scheduleDate=line.date.strftime('%d%m%Y'),
                        identifier="ID%s" % line.own_number,
                        lineNumber=LineNumberO(line.communication)
                    )
                elif line.release_form_id.code == "13":
                    payment = UtilityPayment()
                    payment.setPayment(
                        sender=sender,
                        scheduleDate=line.date.strftime('%d%m%Y'),
                        identifier="ID%s" % line.own_number,
                        lineNumber=LineNumberO(line.communication)
                    )
                else:
                    continue
                lot.add(register=payment)

            file.addLot(lot)
            return file.toString().encode()

    @staticmethod
    def gerar_remessa(order):
        cnab_type = order.payment_mode_id.payment_method_id.code

        if cnab_type == '240':
            if order.payment_mode_id.service_type == '01':
                return Cnab._prepare_charge(order)
            else:
                return Cnab._prepare_sispag(order)

    @staticmethod
    def parse_retorno(file_path):
        file = open(file_path, "r")

        responses = SlipParser.parseFile(file)

        for response in responses:
            pass


