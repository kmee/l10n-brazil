# -*- coding: utf-8 -*-
# ###########################################################################
#
#    Author: Wagner Pereira
#    Copyright 2018 ABGF - www.abgf.gov.br
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


{
    'name': 'Sped e-Social',
    'version': '8.0.0.0.1',
    'category': 'Base',
    'license': 'AGPL-3',
    'author': 'ABGF',
    'website': 'http://www.abgf.gov.br',
    'depends': [
        'sped_transmissao',
        'l10n_br_hr_payroll',
        'l10n_br_hr',
        'hr_contract',
        'resource',
    ],
    'data': [

        # Menus
        'views/sped_esocial_menu.xml',

        # Views
        'wizards/s2299_desligamento_wizard_view.xml',
        'views/sped_esocial_view.xml',
        'views/inherited_res_company.xml',
        'views/inherited_hr_salary_rule.xml',
        'views/inherited_hr_job.xml',
        'views/inherited_hr_contract.xml',
        'views/hr_turnos_trabalho_view.xml',
        'views/inherited_resource_calendar_attendance.xml',
        'views/inherited_hr_employee.xml',
        'views/inherited_res_partner.xml',
        'views/inherited_hr_payslip_view.xml',

        # Intermediarios
        'views/intermediarios/s1000_informacoes_do_empregador_contribuinte_orgao_publico.xml',
        'views/intermediarios/s1005_estabelecimentos_obras_unidades_orgaos_publicos.xml',
        'views/intermediarios/s1010_rubrica_view.xml',
        'views/intermediarios/s1020_lotacao_tributaria_view.xml',
        'views/intermediarios/s1030_cargos_empregos_publicos_view.xml',
        'views/intermediarios/s1050_turnos_trabalho_view.xml',
        'views/intermediarios/s2200_cadastramento_inicial_vinculo_admissao_trabalhador_view.xml',
        'views/intermediarios/s2299_desligamento_view.xml',

        # Segurança
        # 'security/ir.model.access.csv',

    ],
    "installable": True,
    "auto_install": False,
}
