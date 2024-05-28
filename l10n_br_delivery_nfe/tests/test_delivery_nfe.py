# Copyright (C) 2024 Diego Paradeda - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo.addons.l10n_br_stock_account.tests.common import TestBrPickingInvoicingCommon


class TestDeliveryNFe(TestBrPickingInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    # Testing Lucro Presumido - wo pack
    def test_invoicing_picking_volume_lucro_presumido(self):
        """Test Invoicing Picking NFe volume - Lucro Presumido"""
        self.invoice_model = self.env["account.move"]
        self.invoice_wizard = self.env["stock.invoice.onshipping"]
        self.prod1 = self.env.ref("product.product_product_12")
        self.prod2 = self.env.ref("product.product_product_16")
        self._change_user_company(self.env.ref("l10n_br_base.empresa_lucro_presumido"))
        picking = self.env.ref("l10n_br_stock_account.lucro_presumido-picking_1")

        # Set product volume data
        self.prod1.product_nfe40_esp = ""
        self.prod1.product_nfe40_marca = "marca teste"
        self.prod2.product_nfe40_esp = "esp2 teste"
        self.prod2.product_nfe40_marca = "marca2 teste"
        self.prod1.weight = 1
        self.prod2.weight = 3
        self.prod1.net_weight = 1
        self.prod2.net_weight = 5

        # Invoice
        picking.set_to_be_invoiced()
        self.picking_move_state(picking)

        self.assertEqual(picking.state, "done")
        wizard_obj = self.invoice_wizard.with_context(
            active_ids=picking.ids,
            active_model=picking._name,
            active_id=picking.id,
        )
        fields_list = wizard_obj.fields_get().keys()
        wizard_values = wizard_obj.default_get(fields_list)
        wizard = wizard_obj.create(wizard_values)
        wizard.onchange_group()

        self.assertEqual(
            wizard.vol_ids.mapped("nfe40_esp"),
            ["esp2 teste"],
            "Unexpected value for the field nfe40_esp in Stock Invoice Onshipping.",
        )
        self.assertEqual(
            wizard.vol_ids.mapped("nfe40_marca"),
            ["marca2 teste"],
            "Unexpected value for the field nfe40_marca in Stock Invoice Onshipping.",
        )
        self.assertEqual(
            wizard.vol_ids.mapped("nfe40_pesoB"),
            [8],
            "Unexpected value for the field nfe40_pesoB in Stock Invoice Onshipping.",
        )
        self.assertEqual(
            wizard.vol_ids.mapped("nfe40_pesoL"),
            [12],
            "Unexpected value for the field nfe40_pesoL in Stock Invoice Onshipping.",
        )
        self.assertEqual(
            wizard.vol_ids.mapped("nfe40_qVol"),
            ["4.0"],
            "Unexpected value for the field nfe40_qVol in Stock Invoice Onshipping.",
        )

        wizard.fiscal_operation_journal = False
        wizard.action_generate()

        self.assertEqual(picking.invoice_state, "invoiced")

        # Fiscal details
        volume_ids = picking.invoice_ids.fiscal_document_id.nfe40_vol
        self.assertEqual(
            volume_ids.mapped("nfe40_esp"),
            ["esp2 teste"],
            "Unexpected value for the field nfe40_esp in Fiscal Details.",
        )
        self.assertEqual(
            volume_ids.mapped("nfe40_marca"),
            ["marca2 teste"],
            "Unexpected value for the field nfe40_marca in Fiscal Details.",
        )
        self.assertEqual(
            volume_ids.mapped("nfe40_pesoB"),
            [8],
            "Unexpected value for the field nfe40_pesoB in Fiscal Details.",
        )
        self.assertEqual(
            volume_ids.mapped("nfe40_pesoL"),
            [12],
            "Unexpected value for the field nfe40_pesoL in Fiscal Details.",
        )
        self.assertEqual(
            volume_ids.mapped("nfe40_qVol"),
            ["4.0"],
            "Unexpected value for the field nfe40_qVol in Fiscal Details.",
        )

    # Testing Lucro Presumido - with pack
    def test_invoicing_picking_volume_with_package_lucro_presumido(self):
        """Test Invoicing Picking NFe volume - Lucro Presumido - with package"""
        self.invoice_model = self.env["account.move"]
        self.invoice_wizard = self.env["stock.invoice.onshipping"]
        self.prod1 = self.env.ref("product.product_product_12")
        self.prod2 = self.env.ref("product.product_product_16")
        self._change_user_company(self.env.ref("l10n_br_base.empresa_lucro_presumido"))
        picking = self.env.ref("l10n_br_stock_account.lucro_presumido-picking_2")

        # Set product volume data
        self.prod1.product_nfe40_esp = "esp teste"
        self.prod1.product_nfe40_marca = "marca teste"
        self.prod1.weight = 2
        self.prod2.weight = 4
        self.prod1.net_weight = 3
        self.prod2.net_weight = 6

        # Invoice
        picking.set_to_be_invoiced()
        picking.action_confirm()
        # Check product availability
        picking.action_assign()
        # Put in pack
        picking.action_put_in_pack()
        # Validate
        picking.button_validate()

        self.assertEqual(picking.state, "done")
        wizard_obj = self.invoice_wizard.with_context(
            active_ids=picking.ids,
            active_model=picking._name,
            active_id=picking.id,
        )
        fields_list = wizard_obj.fields_get().keys()
        wizard_values = wizard_obj.default_get(fields_list)
        wizard = wizard_obj.create(wizard_values)
        wizard.onchange_group()

        self.assertEqual(
            wizard.vol_ids.mapped("nfe40_esp"),
            ["esp teste"],
            "Unexpected value for the field nfe40_esp in Stock Invoice Onshipping.",
        )
        self.assertEqual(
            wizard.vol_ids.mapped("nfe40_marca"),
            ["marca teste"],
            "Unexpected value for the field nfe40_marca in Stock Invoice Onshipping.",
        )
        self.assertEqual(
            wizard.vol_ids.mapped("nfe40_pesoB"),
            [12],
            "Unexpected value for the field nfe40_pesoB in Stock Invoice Onshipping.",
        )
        self.assertEqual(
            wizard.vol_ids.mapped("nfe40_pesoL"),
            [18],
            "Unexpected value for the field nfe40_pesoL in Stock Invoice Onshipping.",
        )
        self.assertEqual(
            wizard.vol_ids.mapped("nfe40_qVol"),
            ["1"],
            "Unexpected value for the field nfe40_qVol in Stock Invoice Onshipping.",
        )

        wizard.fiscal_operation_journal = False
        wizard.action_generate()

        self.assertEqual(picking.invoice_state, "invoiced")

        # Fiscal details
        volume_ids = picking.invoice_ids.fiscal_document_id.nfe40_vol
        self.assertEqual(
            volume_ids.mapped("nfe40_esp"),
            ["esp teste"],
            "Unexpected value for the field nfe40_esp in Fiscal Details.",
        )
        self.assertEqual(
            volume_ids.mapped("nfe40_marca"),
            ["marca teste"],
            "Unexpected value for the field nfe40_marca in Fiscal Details.",
        )
        self.assertEqual(
            volume_ids.mapped("nfe40_pesoB"),
            [12],
            "Unexpected value for the field nfe40_pesoB in Fiscal Details.",
        )
        self.assertEqual(
            volume_ids.mapped("nfe40_pesoL"),
            [18],
            "Unexpected value for the field nfe40_pesoL in Fiscal Details.",
        )
        self.assertEqual(
            volume_ids.mapped("nfe40_qVol"),
            ["1"],
            "Unexpected value for the field nfe40_qVol in Fiscal Details.",
        )
