from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestWalletCommon


@tagged('post_install', '-at_install')
class TestAffiliateWallet(TestWalletCommon):

    def test_01_payment_out_invoice_by_wallet(self):
        """
        TC01: Pay full customer invoice/refund  by using wallet
        """
        invoice = self.create_invoice(custom_line_vals_list=[{'price_unit': 3000.0}])
        # Check insufficient balance in partner_a's wallet to paid invoice
        with self.assertRaises(UserError):
            self.reconcile_wallet_vs_invoice(self.wallet_type, invoice)
        self.create_payment(
            amount=10000,
            wallet_amount=10000,
            is_wallet=True,
            wallet_type_id=self.wallet_type.id
        )
        wallet_history = self.reconcile_wallet_vs_invoice(self.wallet_type, invoice)
        # Check Invoice
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertRecordValues(wallet_history, [{
            'wallet_type_id': self.wallet_type.id,
            'state': 'done',
            'amount': -3000.0,
        }])
        # Reverse invoice and paid it by using wallet then check same as above
        reverse_wizard = self.env['account.move.reversal'].create({
            'move_ids': [(4, invoice.id)],
            'journal_id': invoice.journal_id.id
        })
        action = reverse_wizard.refund_moves()
        reversed_invoice = self.env['account.move'].browse(action['res_id'])
        reversed_invoice._post()
        wallet_history = self.reconcile_wallet_vs_invoice(self.wallet_type, reversed_invoice)
        # Check Invoice
        self.assertEqual(reversed_invoice.payment_state, 'not_paid')
        self.assertRecordValues(wallet_history, [{
            'wallet_type_id': self.wallet_type.id,
            'state': 'done',
            'amount': 3000.0,
        }])

    def test_02_payment_out_invoice_by_wallet(self):
        """
        TC02: Pay partial customer invoices/refunds by using wallet
        """
        # Top up
        self.create_payment(
            amount=600.0,
            wallet_amount=600.0,
            is_wallet=True,
            wallet_type_id=self.wallet_type.id
        )
        self.create_payment(
            amount=1000.0,
            wallet_amount=1000.0,
            is_wallet=True,
            wallet_type_id=self.wallet_type.id
        )
        # Pay invoice 1
        invoice_1 = self.create_invoice(custom_line_vals_list=[{'price_unit': 500.0}])
        wallet_history_1 = self.reconcile_wallet_vs_invoice(self.wallet_type, invoice_1)
        self.assertEqual(invoice_1.payment_state, 'paid')
        self.assertRecordValues(wallet_history_1, [{
            'wallet_type_id': self.wallet_type.id,
            'state': 'done',
            'amount': -500.0,
        }])
        # Pay invoice 2
        invoice_2 = self.create_invoice(custom_line_vals_list=[{'price_unit': 2000.0}])
        payment = self.create_payment(amount=900.0)
        self.reconcile_payment_vs_invoice(payment, invoice_2)
        self.assertEqual(invoice_2.payment_state, 'partial')
        wallet_history_2 = self.reconcile_wallet_vs_invoice(self.wallet_type, invoice_2)
        self.assertEqual(invoice_2.payment_state, 'paid')
        self.assertRecordValues(wallet_history_2, [{
            'wallet_type_id': self.wallet_type.id,
            'state': 'done',
            'amount': -1100.0,
        }])

    def test_03_payment_in_invoice_by_wallet(self):
        """
        TC03: Pay full vendor bill/refund by using wallet
        """
        invoice = self.create_invoice(
            custom_vals={'move_type': 'in_invoice'},
            custom_line_vals_list=[{'price_unit': 3000.0}]
        )
        wallet_history = self.reconcile_wallet_vs_invoice(self.wallet_type, invoice)
        # Check Invoice
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertRecordValues(wallet_history, [{
            'wallet_type_id': self.wallet_type.id,
            'state': 'done',
            'amount': 3000.0,
        }])
        # Reverse invoice and paid it by using wallet then check same as above
        reverse_wizard = self.env['account.move.reversal'].create({
            'move_ids': [(4, invoice.id)],
            'journal_id': invoice.journal_id.id
        })
        action = reverse_wizard.refund_moves()
        reversed_invoice = self.env['account.move'].browse(action['res_id'])
        reversed_invoice._post()
        wallet_history = self.reconcile_wallet_vs_invoice(self.wallet_type, reversed_invoice)
        # Check Invoice
        self.assertEqual(reversed_invoice.payment_state, 'reversed')
        self.assertRecordValues(wallet_history, [{
            'wallet_type_id': self.wallet_type.id,
            'state': 'done',
            'amount': -3000.0,
        }])

    def test_04_payment_in_invoice_by_wallet(self):
        """
        TC02: Pay partial vendor bill/refund by using wallet
        """
        # Pay invoice 1
        invoice = self.create_invoice(
            custom_vals={'move_type': 'in_invoice'},
            custom_line_vals_list=[{'price_unit': 1000.0}]
        )
        payment = self.create_payment(amount=500.0, payment_type='outbound', partner_type='supplier')
        self.reconcile_payment_vs_invoice(payment, invoice)
        self.assertEqual(invoice.payment_state, 'partial')
        wallet_history = self.reconcile_wallet_vs_invoice(self.wallet_type, invoice)
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertRecordValues(wallet_history, [{
            'wallet_type_id': self.wallet_type.id,
            'state': 'done',
            'amount': 500.0,
        }])
        # Reverse invoice and paid it by using wallet then check same as above
        reverse_wizard = self.env['account.move.reversal'].create({
            'move_ids': [(4, invoice.id)],
            'journal_id': invoice.journal_id.id
        })
        action = reverse_wizard.refund_moves()
        reversed_invoice = self.env['account.move'].browse(action['res_id'])
        reversed_invoice._post()
        payment = self.create_payment(amount=500.0, partner_type='supplier')
        self.reconcile_payment_vs_invoice(payment, reversed_invoice)
        self.assertEqual(reversed_invoice.payment_state, 'partial')
        wallet_history = self.reconcile_wallet_vs_invoice(self.wallet_type, reversed_invoice)
        # Check Invoice
        self.assertEqual(reversed_invoice.payment_state, 'paid')
        self.assertRecordValues(wallet_history, [{
            'wallet_type_id': self.wallet_type.id,
            'state': 'done',
            'amount': -500.0,
        }])
