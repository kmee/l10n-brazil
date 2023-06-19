# Copyright 2018 KMEE INFORMATICA LTDA, Grupo Zenir
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "L10n Br Mdfe",
    "summary": """
        Emissão de Manifesto Eletrônico de Documentos Fiscais (MDF-e)""",
    "version": "14.0.1.0.0",
    "license": "AGPL-3",
    "author": "KMEE INFORMATICA LTDA, Grupo Zenir,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "depends": ["l10n_br_fiscal", "l10n_br_delivery"],
    "external_dependencies": {
        "python": [
            "pynfe.processamento.comunicacao",
            "pynfe.utils",
            "mdfelib.v3_00",
            "erpbrasil.base",
        ],
    },
    "data": [
        "wizard/wizard_mdfe_motivo_cancelamento.xml",
        "views/sped_empresa.xml",
        "views/sped_veiculo.xml",
        "views/l10n_br_mdfe_item.xml",
        "views/sped_documento.xml",
        "views/sped_operacao.xml",
        "views/consultas.xml",
        "security/l10n_br_mdfe_item.xml",
        "security/l10n_br_mdfe_lacre.xml",
        "security/l10n_br_mdfe_condutor.xml",
        "security/sped_documento.xml",
        "security/sped_operacao.xml",
        # 'report/mdfe_report.xml',
    ],
    "demo": [
        "demo/sped_veiculo.xml",
        "demo/l10n_br_mdfe_item.xml",
        "demo/l10n_br_mdfe_seguro.xml",
        "demo/l10n_br_mdfe_lacre.xml",
        "demo/l10n_br_mdfe_condutor.xml",
        "demo/sped_documento.xml",
        "demo/sped_operacao.xml",
    ],
}
