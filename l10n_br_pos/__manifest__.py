# © 2016 KMEE INFORMATICA LTDA (https://kmee.com.br)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Ponto de venda adaptado a legislação Brasileira",
    "version": "16.0.1.0.0",
    "author": "KMEE, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "license": "AGPL-3",
    "category": "Point Of Sale",
    "development_status": "Alpha",
    "maintainers": ["mileo", "lfdivino", "luismalta", "ygcarvalh"],
    "depends": [
        "l10n_br_fiscal",
        "l10n_br_stock",
        "l10n_br_zip",
        "l10n_br_base",
        "point_of_sale",
    ],
    "data": [
        "security/l10n_br_pos_product_fiscal_map.xml",
        "data/l10n_br_fiscal_cfop_data.xml",
        "views/l10n_br_pos_product_fiscal_map.xml",
        "views/pos_order_view.xml",
        "views/product_template_view.xml",
        "views/res_company.xml",
        "views/pos_payment_method_view.xml",
    ],
    "installable": True,
}
