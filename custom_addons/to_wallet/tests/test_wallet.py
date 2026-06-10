import datetime

from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged
from .common import TestWalletCommon


@tagged('post_install', '-at_install')
class TestWallet(TestWalletCommon):

    def test_01_create_non_wallet_payment(self):
        payment = self.create_payment(amount=100000, is_wallet=False)
        receivable_move_line = payment.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(receivable_move_line, [
            {
                'wallet_amount_currency': 0,
                'wallet_amount_residual_currency': 0,
                'non_wallet_amount_currency': -100000,
                'non_wallet_amount_residual_currency': -100000,
            }
        ])
        self.assertItemsEqual(self.partner.commercial_partner_id.mapped('wallet_ids'), [])

    def test_02_create_wallet_payment(self):
        # Top up wallet
        payment = self.create_payment(
            amount=100000,
            wallet_amount=100000,
            is_wallet=True,
            wallet_type_id=self.consumption_wallet_type.id
        )
        with self.assertRaises(ValidationError):
            payment.action_draft()
        receivable_move_line = payment.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(receivable_move_line, [{
            'amount_currency': -100000,
            'amount_residual_currency': -100000,
            'wallet_amount_currency': -100000,
            'wallet_amount_residual_currency': -100000,
            'non_wallet_amount_currency': 0,
            'non_wallet_amount_residual_currency': 0,
        }])
        self.assertRecordValues(self.partner.commercial_partner_id.wallet_ids, [
            {
                'currency_id': self.currency_usd.id,
                'amount': 100000
            }
        ])
        self.assertRecordValues(receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_usd.id,
            'amount': 100000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        # Withdraw wallet
        payment = self.create_payment(
            amount=50000,
            wallet_amount=50000,
            is_wallet=True,
            wallet_type_id=self.consumption_wallet_type.id,
            payment_type='outbound'
        )
        with self.assertRaises(ValidationError):
            payment.action_draft()
        receivable_move_line = payment.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(self.partner.commercial_partner_id.wallet_ids, [
            {
                'currency_id': self.currency_usd.id,
                'amount': 50000
            }
        ])
        self.assertRecordValues(receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_usd.id,
            'amount': -50000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])

    def test_03_wallet_payment_invalid_wallet_amount(self):
        # Check wallet_amount < 0
        self.assertRaises(
            ValidationError,
            self.create_payment,
            amount=100000,
            is_wallet=True,
            wallet_amount=-50000,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        self.assertRaises(
            ValidationError,
            self.create_payment,
            amount=100000,
            is_wallet=True,
            wallet_amount=-50000,
            wallet_type_id=self.consumption_wallet_type.id,
            payment_type='outbound'
        )
        # Check wallet_amount > amount
        self.assertRaises(
            ValidationError,
            self.create_payment,
            amount=100000,
            is_wallet=True,
            wallet_amount=100001,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        self.assertRaises(
            ValidationError,
            self.create_payment,
            amount=100000,
            is_wallet=True,
            wallet_amount=100001,
            wallet_type_id=self.consumption_wallet_type.id,
            payment_type='outbound'
        )
        # Check wallet_amount < amount with
        self.create_payment(
            amount=100000,
            is_wallet=True,
            wallet_amount=50000,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        self.create_payment(
            amount=100000,
            is_wallet=True,
            wallet_amount=50000,
            wallet_type_id=self.consumption_wallet_type.id,
            payment_type='outbound'
        )

    def test_04_wallet_payment_invalid_wallet_configuration(self):
        # Not support top up wallet
        self.consumption_wallet_type.allow_top_up = False
        self.assertRaises(
            ValidationError,
            self.create_payment,
            amount=100000,
            is_wallet=True,
            wallet_amount=100000,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        # Not support withdraw wallet
        self.consumption_wallet_type.allow_withdraw = False
        self.assertRaises(
            ValidationError,
            self.create_payment,
            amount=100000,
            is_wallet=True,
            wallet_amount=100000,
            wallet_type_id=self.consumption_wallet_type.id,
            payment_type='outbound'
        )

    def test_05_create_mix_wallet_payment(self):
        payment = self.create_payment(
            amount=300000,
            is_wallet=True,
            wallet_amount=200000,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        receivable_move_line = payment.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(receivable_move_line, [{
            'amount_currency': -300000,
            'amount_residual_currency': -300000,
            'wallet_amount_currency': -200000,
            'wallet_amount_residual_currency': -200000,
            'non_wallet_amount_currency': -100000,
            'non_wallet_amount_residual_currency': -100000,
        }])
        self.assertRecordValues(self.partner.commercial_partner_id.wallet_ids, [
            {
                'currency_id': self.currency_usd.id,
                'amount': 200000
            }
        ])
        self.assertRecordValues(receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_usd.id,
            'amount': 200000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])

    def test_06_reconcile_invoice_with_lesser_wallet_payment(self):
        invoice = self.create_invoice(custom_line_vals_list=[{'price_unit': 200000}])
        payment = self.create_payment(
            amount=100000,
            wallet_amount=100000,
            is_wallet=True,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        invoice_receivable_move_line = invoice.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(invoice_receivable_move_line, [{
            'amount_currency': 200000,
            'amount_residual_currency': 200000,
            'wallet_amount_currency': 0,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 200000,
            'non_wallet_amount_residual_currency': 200000,
        }])
        payment_receivable_move_line = payment.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(payment_receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_usd.id,
            'amount': 100000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.reconcile_payment_vs_invoice(payment, invoice)
        self.assertEqual(invoice.payment_state, 'partial')
        self.assertRecordValues(invoice_receivable_move_line, [{
            'amount_currency': 200000,
            'amount_residual_currency': 100000,
            'wallet_amount_currency': 100000,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 100000,
            'non_wallet_amount_residual_currency': 100000,
        }])
        self.assertRecordValues(payment_receivable_move_line, [{
            'amount_currency': -100000,
            'amount_residual_currency': 0,
            'wallet_amount_currency': -100000,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 0,
            'non_wallet_amount_residual_currency': 0,
        }])
        self.assertRecordValues(invoice_receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_usd.id,
            'amount': -100000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.assertEqual(self.partner.commercial_partner_id.wallet_ids.amount, 0)

    def test_07_reconcile_invoice_with_greater_wallet_payment(self):
        invoice = self.create_invoice(custom_line_vals_list=[{'price_unit': 100000}])
        payment = self.create_payment(
            amount=200000,
            wallet_amount=200000,
            is_wallet=True,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        invoice_receivable_move_line = invoice.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(invoice_receivable_move_line, [{
            'amount_currency': 100000,
            'amount_residual_currency': 100000,
            'wallet_amount_currency': 0,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 100000,
            'non_wallet_amount_residual_currency': 100000,
        }])
        payment_receivable_move_line = payment.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(payment_receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_usd.id,
            'amount': 200000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.reconcile_payment_vs_invoice(payment, invoice)
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertRecordValues(invoice_receivable_move_line, [{
            'amount_currency': 100000,
            'amount_residual_currency': 0,
            'wallet_amount_currency': 100000,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 0,
            'non_wallet_amount_residual_currency': 0,
        }])
        self.assertRecordValues(payment_receivable_move_line, [{
            'amount_currency': -200000,
            'amount_residual_currency': -100000,
            'wallet_amount_currency': -200000,
            'wallet_amount_residual_currency': -100000,
            'non_wallet_amount_currency': 0,
            'non_wallet_amount_residual_currency': 0,
        }])
        self.assertRecordValues(invoice_receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_usd.id,
            'amount': -100000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.assertEqual(self.partner.commercial_partner_id.wallet_ids.amount, 100000)

    def test_08_reconcile_invoice_with_mix_wallet_payment(self):
        invoice = self.create_invoice(custom_line_vals_list=[{'price_unit': 100000}])
        payment = self.create_payment(
            amount=100000,
            wallet_amount=50000,
            is_wallet=True,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        invoice_receivable_move_line = invoice.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(invoice_receivable_move_line, [{
            'amount_currency': 100000,
            'amount_residual_currency': 100000,
            'wallet_amount_currency': 0,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 100000,
            'non_wallet_amount_residual_currency': 100000,
        }])
        payment_receivable_move_line = payment.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(payment_receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_usd.id,
            'amount': 50000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.reconcile_payment_vs_invoice(payment, invoice)
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertRecordValues(invoice_receivable_move_line, [{
            'amount_currency': 100000,
            'amount_residual_currency': 0,
            'wallet_amount_currency': 50000,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 50000,
            'non_wallet_amount_residual_currency': 0,
        }])
        self.assertRecordValues(payment_receivable_move_line, [{
            'amount_currency': -100000,
            'amount_residual_currency': 0,
            'wallet_amount_currency': -50000,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': -50000,
            'non_wallet_amount_residual_currency': 0,
        }])
        self.assertRecordValues(invoice_receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_usd.id,
            'amount': -50000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.assertEqual(self.partner.commercial_partner_id.wallet_ids.amount, 0)

    def test_09_reconcile_invoice_with_mix_wallet_payment(self):
        invoice = self.create_invoice(custom_line_vals_list=[{'price_unit': 10000}])
        payment = self.create_payment(
            amount=100000,
            wallet_amount=50000,
            is_wallet=True,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        invoice_receivable_move_line = invoice.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(invoice_receivable_move_line, [{
            'amount_currency': 10000,
            'amount_residual_currency': 10000,
            'wallet_amount_currency': 0,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 10000,
            'non_wallet_amount_residual_currency': 10000,
        }])
        payment_receivable_move_line = payment.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(payment_receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_usd.id,
            'amount': 50000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.reconcile_payment_vs_invoice(payment, invoice)
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertRecordValues(invoice_receivable_move_line, [{
            'amount_currency': 10000,
            'amount_residual_currency': 0,
            'wallet_amount_currency': 0,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 10000,
            'non_wallet_amount_residual_currency': 0,
        }])
        self.assertRecordValues(payment_receivable_move_line, [{
            'amount_currency': -100000,
            'amount_residual_currency': -90000,
            'wallet_amount_currency': -50000,
            'wallet_amount_residual_currency': -50000,
            'non_wallet_amount_currency': -50000,
            'non_wallet_amount_residual_currency': -40000,
        }])
        self.assertFalse(invoice_receivable_move_line.wallet_history_ids)
        self.assertEqual(self.partner.commercial_partner_id.wallet_ids.amount, 50000)

    def test_10_reconcile_invoice_with_mix_wallet_payment(self):
        invoice = self.create_invoice(custom_line_vals_list=[{'price_unit': 10000}])
        payment = self.create_payment(
            amount=100000,
            wallet_amount=50000,
            is_wallet=True,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        invoice_receivable_move_line = invoice.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(invoice_receivable_move_line, [{
            'amount_currency': 10000,
            'amount_residual_currency': 10000,
            'wallet_amount_currency': 0,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 10000,
            'non_wallet_amount_residual_currency': 10000,
        }])
        payment_receivable_move_line = payment.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(payment_receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_usd.id,
            'amount': 50000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.reconcile_payment_vs_invoice(payment, invoice, force_pay_by_wallet=True)
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertRecordValues(invoice_receivable_move_line, [{
            'amount_currency': 10000,
            'amount_residual_currency': 0,
            'wallet_amount_currency': 10000,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 0,
            'non_wallet_amount_residual_currency': 0,
        }])
        self.assertRecordValues(payment_receivable_move_line, [{
            'amount_currency': -100000,
            'amount_residual_currency': -90000,
            'wallet_amount_currency': -50000,
            'wallet_amount_residual_currency': -40000,
            'non_wallet_amount_currency': -50000,
            'non_wallet_amount_residual_currency': -50000,
        }])
        self.assertRecordValues(invoice_receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_usd.id,
            'amount': -10000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.assertEqual(self.partner.commercial_partner_id.wallet_ids.amount, 40000)

    def test_11_reconcile_invoice_with_wallet_payment_other_currency(self):
        invoice = self.create_invoice(custom_line_vals_list=[{'price_unit': 100}])
        payment = self.create_payment(
            amount=100000,
            wallet_amount=100000,
            is_wallet=True,
            currency_id=self.currency_vnd.id,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        invoice_receivable_move_line = invoice.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(invoice_receivable_move_line, [{
            'currency_id': self.currency_usd.id,
            'amount_currency': 100,
            'amount_residual_currency': 100,
            'wallet_amount_currency': 0,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 100,
            'non_wallet_amount_residual_currency': 100,
        }])
        payment_receivable_move_line = payment.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(payment_receivable_move_line, [{
            'currency_id': self.currency_vnd.id,
            'amount_currency': -100000,
            'amount_residual_currency': -100000,
            'wallet_amount_currency': -100000,
            'wallet_amount_residual_currency': -100000,
            'non_wallet_amount_currency': 0,
            'non_wallet_amount_residual_currency': 0,
        }])
        self.assertRecordValues(payment_receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_vnd.id,
            'amount': 100000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.assertEqual(self.partner.commercial_partner_id.wallet_ids.amount, 100000)
        self.assertRaises(ValidationError, self.reconcile_payment_vs_invoice, payment=payment, invoice=invoice)

    def test_12_reconcile_invoice_with_wallet_payment_other_currency(self):
        invoice = self.create_invoice(custom_line_vals_list=[{'price_unit': 100}])
        payment = self.create_payment(
            amount=100000,
            wallet_amount=100000,
            is_wallet=True,
            currency_id=self.currency_vnd.id,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        invoice_receivable_move_line = invoice.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(invoice_receivable_move_line, [{
            'currency_id': self.currency_usd.id,
            'amount_currency': 100,
            'amount_residual_currency': 100,
            'wallet_amount_currency': 0,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 100,
            'non_wallet_amount_residual_currency': 100,
        }])
        payment_receivable_move_line = payment.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(payment_receivable_move_line, [{
            'currency_id': self.currency_vnd.id,
            'amount_currency': -100000,
            'amount_residual_currency': -100000,
            'wallet_amount_currency': -100000,
            'wallet_amount_residual_currency': -100000,
            'non_wallet_amount_currency': 0,
            'non_wallet_amount_residual_currency': 0,
        }])
        self.assertRecordValues(payment_receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_vnd.id,
            'amount': 100000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.assertEqual(self.partner.commercial_partner_id.wallet_ids.amount, 100000)
        self.assertRaises(ValidationError, self.reconcile_payment_vs_invoice, payment=payment, invoice=invoice)

    def test_13_full_reconcile(self):
        invoice = self.create_invoice(custom_line_vals_list=[{'price_unit': 100000}])
        payment = self.create_payment(
            amount=100000,
            wallet_amount=100000,
            is_wallet=True,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        invoice_receivable_move_line = invoice.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(invoice_receivable_move_line, [{
            'amount_currency': 100000,
            'amount_residual_currency': 100000,
            'wallet_amount_currency': 0,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 100000,
            'non_wallet_amount_residual_currency': 100000,
        }])
        payment_receivable_move_line = payment.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(payment_receivable_move_line, [{
            'amount_currency': -100000,
            'amount_residual_currency': -100000,
            'wallet_amount_currency': -100000,
            'wallet_amount_residual_currency': -100000,
            'non_wallet_amount_currency': 0,
            'non_wallet_amount_residual_currency': 0,
        }])
        self.reconcile_payment_vs_invoice(payment, invoice)
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertRecordValues(invoice_receivable_move_line, [{
            'amount_currency': 100000,
            'amount_residual_currency': 0,
            'wallet_amount_currency': 100000,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 0,
            'non_wallet_amount_residual_currency': 0,
        }])
        payment_receivable_move_line = payment.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(payment_receivable_move_line, [{
            'amount_currency': -100000,
            'amount_residual_currency': 0,
            'wallet_amount_currency': -100000,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 0,
            'non_wallet_amount_residual_currency': 0,
        }])
        self.assertRecordValues(payment_receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_usd.id,
            'amount': 100000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.assertRecordValues(invoice_receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_usd.id,
            'amount': -100000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.assertTrue(invoice_receivable_move_line.full_reconcile_id)
        self.assertTrue(payment_receivable_move_line.full_reconcile_id)
        self.assertEqual(invoice_receivable_move_line.full_reconcile_id, payment_receivable_move_line.full_reconcile_id)

    def test_14_full_reconcile_exchange_rate(self):
        invoice = self.create_invoice(
            custom_vals={'currency_id': self.currency_eur.id},
            custom_line_vals_list=[{'price_unit': 100}]
        )
        amount_receivable = abs(sum(invoice.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable').mapped('amount_currency')))
        payment = self.create_payment(
            amount=amount_receivable,
            wallet_amount=amount_receivable,
            is_wallet=True,
            currency_id=self.currency_eur.id,
            date=datetime.date(self.current_year + 1, 1, 1),
            wallet_type_id=self.consumption_wallet_type.id,
        )
        self.reconcile_payment_vs_invoice(payment, invoice)
        self.assertEqual(invoice.payment_state, 'paid')
        invoice_receivable_move_line = invoice.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(invoice_receivable_move_line, [{
            'amount_currency': 100,
            'amount_residual_currency': 0,
            'wallet_amount_currency': 100,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 0,
            'non_wallet_amount_residual_currency': 0,
        }])
        payment_receivable_move_line = payment.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(payment_receivable_move_line, [{
            'amount_currency': -100,
            'amount_residual_currency': 0,
            'wallet_amount_currency': -100,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 0,
            'non_wallet_amount_residual_currency': 0,
        }])
        self.assertRecordValues(payment_receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_eur.id,
            'amount': 100,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.assertRecordValues(invoice_receivable_move_line.wallet_history_ids, [{
            'currency_id': self.currency_eur.id,
            'amount': -100,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.assertTrue(invoice_receivable_move_line.full_reconcile_id)
        self.assertTrue(payment_receivable_move_line.full_reconcile_id)
        self.assertEqual(invoice_receivable_move_line.full_reconcile_id, payment_receivable_move_line.full_reconcile_id)
        exchange_line = invoice_receivable_move_line.full_reconcile_id.reconciled_line_ids.filtered(
            lambda r: r.journal_id == r.company_id.currency_exchange_journal_id
        )
        self.assertRecordValues(exchange_line, [{'debit': 10, 'credit': 0}])

    def test_15_reconcile_invoice_with_multiple_payments(self):
        payment1 = self.create_payment(
            amount=1956014,
            wallet_amount=1956014,
            is_wallet=True,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        payment1_receivable_move_lines = payment1.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        payment2 = self.create_payment(
            amount=1999000,
            wallet_amount=1999000,
            is_wallet=True,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        payment2_receivable_move_lines = payment2.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        invoice = self.create_invoice(custom_line_vals_list=[{'price_unit': 1999000}])
        invoice_payable_lines = invoice.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        (invoice_payable_lines + payment1_receivable_move_lines + payment2_receivable_move_lines).reconcile()
        self.assertRecordValues(invoice, [{'payment_state': 'paid'}])
        self.assertRecordValues(payment1_receivable_move_lines, [{'wallet_amount_residual_currency': -1956014}])
        self.assertFalse(payment1_receivable_move_lines.matched_debit_ids)
        self.assertRecordValues(payment2_receivable_move_lines, [{'wallet_amount_residual_currency': 0}])
        self.assertRecordValues(payment2_receivable_move_lines.matched_debit_ids, [{'amount': 1999000}])

    def test_16_reconcile_multiple_invoices_with_multiple_payments(self):
        payment1 = self.create_payment(
            amount=1000000,
            wallet_amount=1000000,
            is_wallet=True,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        payment1_receivable_move_lines = payment1.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        invoice1 = self.create_invoice(custom_line_vals_list=[{'price_unit': 100000}])
        invoice1_payable_lines = invoice1.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        (invoice1_payable_lines + payment1_receivable_move_lines).reconcile()
        self.assertRecordValues(invoice1, [{'payment_state': 'paid'}])

        payment2 = self.create_payment(
            amount=2000000,
            wallet_amount=2000000,
            is_wallet=True,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        payment2_receivable_move_lines = payment2.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        invoice2 = self.create_invoice(custom_line_vals_list=[{'price_unit': 1999000}])
        invoice2_payable_lines = invoice2.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        (invoice2_payable_lines + payment1_receivable_move_lines + payment2_receivable_move_lines).reconcile()
        self.assertRecordValues(invoice2, [{'payment_state': 'paid'}])
        self.assertRecordValues(payment1_receivable_move_lines, [{'wallet_amount_residual_currency': -900000}])
        self.assertRecordValues(payment1_receivable_move_lines.matched_debit_ids, [{'amount': 100000}])
        self.assertRecordValues(payment2_receivable_move_lines, [{'wallet_amount_residual_currency': -1000}])
        self.assertRecordValues(payment2_receivable_move_lines.matched_debit_ids, [{'amount': 1999000}])

    def _create_manual_journal_entry(self, amount, wallet_amount):
        wallet = self.partner._create_wallet_if_not_exist(self.consumption_wallet_type)
        entry = self.env['account.move'].create({
            'line_ids': [
                (0, 0, {
                    'account_id': self.account_112.id,
                    'partner_id': self.partner.id,
                    'debit': amount,
                    'credit': 0.0
                }),
                (0, 0, {
                    'account_id': self.account_131.id,
                    'partner_id': self.partner.id,
                    'debit': 0.0,
                    'credit': amount,
                    'wallet_id': wallet.id,
                    'wallet_amount_currency': -1 * wallet_amount,
                })
            ]
        })
        entry._post()
        return entry

    def test_17_top_up_zero_wallet_amount_from_manual_journal_entry(self):
        entry = self._create_manual_journal_entry(1000000, 0)
        self.assertRecordValues(entry.line_ids, [{
            'account_id': self.account_112.id,
            'partner_id': self.partner.id,
            'debit': 1000000,
            'credit': 0,
            'wallet_amount_currency': 0,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 1000000,
            'non_wallet_amount_residual_currency': 1000000,
        }, {
            'account_id': self.account_131.id,
            'partner_id': self.partner.id,
            'debit': 0,
            'credit': 1000000,
            'wallet_amount_currency': 0,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': -1000000,
            'non_wallet_amount_residual_currency': -1000000,
        }])
        self.assertEqual(self.partner.commercial_partner_id.wallet_ids.amount, 0)

    def test_18_top_up_non_zero_wallet_amount_from_manual_journal_entry(self):
        entry = self._create_manual_journal_entry(1000000, 600000)
        self.assertRecordValues(entry.line_ids, [{
            'account_id': self.account_112.id,
            'partner_id': self.partner.id,
            'debit': 1000000,
            'credit': 0,
            'wallet_amount_currency': 0,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 1000000,
            'non_wallet_amount_residual_currency': 1000000,
        }, {
            'account_id': self.account_131.id,
            'partner_id': self.partner.id,
            'debit': 0,
            'credit': 1000000,
            'wallet_amount_currency': -600000,
            'wallet_amount_residual_currency': -600000,
            'non_wallet_amount_currency': -400000,
            'non_wallet_amount_residual_currency': -400000,
        }])
        wallets = self.partner.commercial_partner_id.wallet_ids
        self.assertRecordValues(wallets.wallet_history_ids, [{
            'currency_id': self.currency_usd.id,
            'amount': 600000,
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.assertRecordValues(wallets, [{'amount': 600000}])

    def test_19_withdraw_wallet(self):
        self.create_payment(
            amount=100000,
            is_wallet=True,
            wallet_amount=100000,
            wallet_type_id=self.consumption_wallet_type.id
        )
        self.create_payment(
            amount=10000,
            is_wallet=True,
            wallet_amount=10000,
            payment_type='outbound',
            wallet_type_id=self.consumption_wallet_type.id
        )
        wallets = self.partner.commercial_partner_id.wallet_ids
        self.assertRecordValues(wallets.wallet_history_ids, [
            {
                'currency_id': self.currency_usd.id,
                'amount': 100000,
                'state': 'done',
                'wallet_type_id': self.consumption_wallet_type.id
            },
            {
                'currency_id': self.currency_usd.id,
                'amount': -10000,
                'state': 'done',
                'wallet_type_id': self.consumption_wallet_type.id
            },
        ])
        self.assertRecordValues(self.partner.commercial_partner_id.wallet_ids, [{'amount': 90000}])
        # test in case that withdrawing money much more than money in wallet
        self.assertRaises(ValidationError, self.create_payment, amount=100000, payment_type='outbound', is_wallet=True, wallet_amount=100000)
        # test in case not exist wallet to withdraw
        self.assertRaises(ValidationError, self.create_payment, amount=100000, payment_type='outbound', is_wallet=True, wallet_amount=100000, currency_id=self.currency_usd.id)

    def test_20_register_payment_exceed_invoice_due_amount(self):
        """
        Using register payment wizard to record an exceeded amount payment and transfer residual amount to partner's wallet
        """
        invoice = self.create_invoice(custom_line_vals_list=[{'price_unit': 25000}, {'price_unit': 100000}])
        payments = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=invoice.ids).create({
            'is_wallet': True,
            'amount': 150000,
            'payment_difference_handling': 'open',
            'wallet_type_id': self.consumption_wallet_type.id
        })._create_payments()
        self.assertRecordValues(payments, [{
            'amount': 150000,
            'is_wallet': True,
            'wallet_amount': 25000
        }])
        self.assertRecordValues(payments.wallet_id.wallet_history_ids, [
            {
                'currency_id': self.currency_usd.id,
                'amount': 25000,
                'state': 'done',
                'wallet_type_id': self.consumption_wallet_type.id
            }
        ])
        self.assertRecordValues(payments.wallet_id, [{'amount': 25000}])

    def test_21_register_payment_partial_reconcile(self):
        """
        Using register payment wizard to record a partial payment -> no transfer amount created and payment will be a normal payment
        """
        invoice = self.create_invoice(custom_line_vals_list=[{'price_unit': 25000}, {'price_unit': 100000}])
        payments = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=invoice.ids).create({
            'is_wallet': True,
            'amount': 65000,
            'wallet_type_id': self.consumption_wallet_type.id
        })._create_payments()
        self.assertRecordValues(payments, [{
            'amount': 65000,
            'wallet_amount': 0.0,
            'is_wallet': False,
        }])

    def test_22_register_payment_currency(self):
        invoice = self.create_invoice(custom_line_vals_list=[{'price_unit': 121000}, {'price_unit': 110000}])
        with self.assertRaises(ValidationError):
            self.env['account.payment.register'].with_context(active_model='account.move', active_ids=invoice.ids).create({
                'is_wallet': True,
                'amount': 300000,
                'payment_difference_handling': 'open',
                'wallet_type_id': self.consumption_wallet_type.id,
                'currency_id': self.currency_eur.id,
            })._create_payments()

    def test_23_register_payment_from_batch(self):
        invoice_1 = self.create_invoice(custom_line_vals_list=[{'price_unit': 25000}, {'price_unit': 100000}])
        invoice_2 = self.create_invoice(custom_line_vals_list=[{'price_unit': 25000}, {'price_unit': 100000}])
        payments = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=(invoice_1 + invoice_2).ids
        ).create({})._create_payments()
        self.assertRecordValues(payments, [{
            'amount': 125000,
            'is_wallet': False,
            'wallet_amount': 0
        }, {
            'amount': 125000,
            'is_wallet': False,
            'wallet_amount': 0
        }])

    def test_24_register_group_payment(self):
        invoice_1 = self.create_invoice(custom_line_vals_list=[{'price_unit': 25000}, {'price_unit': 100000}])
        invoice_2 = self.create_invoice(custom_line_vals_list=[{'price_unit': 25000}, {'price_unit': 100000}])
        payments = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=(invoice_1 + invoice_2).ids
        ).create({
            'amount': 300000,
            'payment_difference_handling': 'open',
            'is_wallet': True,
            'wallet_type_id': self.consumption_wallet_type.id,
            'group_payment': True
        })._create_payments()
        self.assertRecordValues(payments, [{
            'amount': 300000,
            'is_wallet': True,
            'wallet_amount': 50000
        }])
        invoice_receivable_move_line_1 = invoice_1.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(invoice_receivable_move_line_1, [{
            'amount_currency': 125000,
            'amount_residual_currency': 0,
            'wallet_amount_currency': 0,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 125000,
            'non_wallet_amount_residual_currency': 0,
        }])
        invoice_receivable_move_line_2 = invoice_2.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(invoice_receivable_move_line_2, [{
            'amount_currency': 125000,
            'amount_residual_currency': 0,
            'wallet_amount_currency': 0,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': 125000,
            'non_wallet_amount_residual_currency': 0,
        }])
        self.assertRecordValues(payments.wallet_id.wallet_history_ids, [
            {
                'currency_id': self.currency_usd.id,
                'amount': 50000,
                'state': 'done',
                'wallet_type_id': self.consumption_wallet_type.id
            },
        ])

    def test_25_multi_invoice_multi_payment_complex(self):
        self.cr.execute("UPDATE res_company SET currency_id = %s WHERE id = %s", [self.currency_vnd.id, self.env.company.id])
        self.env.invalidate_all()
        self.env['res.currency.rate'].search([]).unlink()
        currency_rate_vals = [
            {
                'name': '2022-01-01',
                'rate': 1,
                'currency_id': self.currency_vnd.id
            },
            {
                'name': '2022-01-01',
                'inverse_company_rate': 22530,
                'currency_id': self.currency_usd.id
            },
            {
                'name': '2022-01-15',
                'inverse_company_rate': 23450,
                'currency_id': self.currency_usd.id
            },
            {
                'name': '2022-01-30',
                'inverse_company_rate': 23970,
                'currency_id': self.currency_usd.id
            },
            {
                'name': '2022-02-10',
                'inverse_company_rate': 22150,
                'currency_id': self.currency_usd.id
            },
            {
                'name': '2022-02-20',
                'inverse_company_rate': 24230,
                'currency_id': self.currency_usd.id
            },
            {
                'name': '2022-02-22',
                'inverse_company_rate': 23130,
                'currency_id': self.currency_usd.id
            },
            {
                'name': '2022-03-10',
                'inverse_company_rate': 24560,
                'currency_id': self.currency_usd.id
            },
            {
                'name': '2022-03-15',
                'inverse_company_rate': 24270,
                'currency_id': self.currency_usd.id
            },
            {
                'name': '2022-03-20',
                'inverse_company_rate': 24670,
                'currency_id': self.currency_usd.id
            },
        ]
        self.env['res.currency.rate'].create(currency_rate_vals)
        invoice1 = self.create_invoice(
            custom_vals={
                'currency_id': self.currency_usd.id,
                'date': '2022-01-01'
            },
            custom_line_vals_list=[{'price_unit': 69}]
        )
        invoice2 = self.create_invoice(
            custom_vals={
                'currency_id': self.currency_usd.id,
                'date': '2022-01-30'
            },
            custom_line_vals_list=[{'price_unit': 69}]
        )
        invoice3 = self.create_invoice(
            custom_vals={
                'currency_id': self.currency_usd.id,
                'date': '2022-03-10'
            },
            custom_line_vals_list=[{'price_unit': 69}]
        )
        payment1 = self.create_payment(
            amount=65,
            is_wallet=True,
            wallet_amount=65,
            date='2022-01-15',
            wallet_type_id=self.consumption_wallet_type.id
        )
        payment2 = self.create_payment(
            amount=70,
            is_wallet=True,
            wallet_amount=70,
            date='2022-02-10',
            wallet_type_id=self.consumption_wallet_type.id
        )
        payment3 = self.create_payment(
            amount=31.5,
            is_wallet=True,
            wallet_amount=31.5,
            date='2022-02-20',
            wallet_type_id=self.consumption_wallet_type.id
        )
        payment4 = self.create_payment(
            amount=27,
            is_wallet=True,
            wallet_amount=27,
            date='2022-02-28',
            wallet_type_id=self.consumption_wallet_type.id
        )
        payment5 = self.create_payment(
            amount=33.5,
            is_wallet=True,
            wallet_amount=33.5,
            date='2022-03-20',
            wallet_type_id=self.consumption_wallet_type.id
        )

        (invoice1.line_ids | payment1.line_ids).filtered(lambda l: l.account_id.account_type == 'asset_receivable').reconcile()
        self.assertNotEqual(invoice1.payment_state, 'paid')
        (invoice1.line_ids | payment2.line_ids).filtered(lambda l: l.account_id.account_type == 'asset_receivable').reconcile()
        self.assertEqual(invoice1.payment_state, 'paid')
        (invoice2.line_ids | payment2.line_ids).filtered(lambda l: l.account_id.account_type == 'asset_receivable').reconcile()
        self.assertNotEqual(invoice2.payment_state, 'paid')
        (invoice2.line_ids | payment3.line_ids).filtered(lambda l: l.account_id.account_type == 'asset_receivable').reconcile()
        self.assertEqual(invoice2.payment_state, 'paid')
        (invoice3.line_ids | payment3.line_ids).filtered(lambda l: l.account_id.account_type == 'asset_receivable').reconcile()
        self.assertNotEqual(invoice3.payment_state, 'paid')
        (invoice3.line_ids | payment4.line_ids).filtered(lambda l: l.account_id.account_type == 'asset_receivable').reconcile()
        self.assertNotEqual(invoice3.payment_state, 'paid')
        (invoice3.line_ids | payment5.line_ids).filtered(lambda l: l.account_id.account_type == 'asset_receivable').reconcile()
        self.assertEqual(invoice3.payment_state, 'paid')

    def test_26_adjust_wallet_amount_onpayment_before_confirm(self):
        vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'payment_method_id': self.account_payment_method_manual_in.id,
            'journal_id': self.bank_journal_usd.id,
            'date': datetime.date(self.current_year - 1, 1, 1),
            'is_wallet': True,
            'amount': 150000,
            'wallet_amount': 100000,
            'wallet_type_id': self.consumption_wallet_type.id
        }
        payment = self.env['account.payment'].create(vals)
        receivable_move_line = payment.line_ids.filtered(lambda r: r.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(receivable_move_line, [{
            'amount_currency': -150000,
            'amount_residual_currency': -150000,
            'wallet_amount_currency': -100000,
            'wallet_amount_residual_currency': -100000,
            'non_wallet_amount_currency': -50000,
            'non_wallet_amount_residual_currency': -50000,
        }])
        payment_form = Form(payment)
        payment_form.wallet_amount = 50000
        payment_form.save()
        payment.action_post()
        self.assertRecordValues(receivable_move_line, [{
            'amount_currency': -150000,
            'amount_residual_currency': -150000,
            'wallet_amount_currency': -50000,
            'wallet_amount_residual_currency': -50000,
            'non_wallet_amount_currency': -100000,
            'non_wallet_amount_residual_currency': -100000,
        }])

    def test_27_edit_payment(self):
        new_partner = self.env['res.partner'].create({'name': 'New Partner'})
        self.assertFalse(new_partner.wallet_ids)

        payment1 = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': new_partner.id,
            'is_wallet': False,
            'amount': 500
        })
        receivable_move_line = payment1.move_id.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        self.assertRecordValues(receivable_move_line, [{
            'amount_currency': -500,
            'amount_residual_currency': -500,
            'wallet_amount_currency': 0,
            'wallet_amount_residual_currency': 0,
            'non_wallet_amount_currency': -500,
            'non_wallet_amount_residual_currency': -500,
        }])
        self.assertFalse(new_partner.wallet_ids)
        payment1.write({'is_wallet': True, 'wallet_amount': 500, 'wallet_type_id': self.consumption_wallet_type.id})
        self.assertRecordValues(receivable_move_line, [{
            'amount_currency': -500,
            'amount_residual_currency': -500,
            'wallet_amount_currency': -500,
            'wallet_amount_residual_currency': -500,
            'non_wallet_amount_currency': 0,
            'non_wallet_amount_residual_currency': 0,
        }])
        self.assertFalse(new_partner.wallet_ids)

        payment1.action_post()
        self.assertEqual(new_partner.wallet_ids[0].amount, 500)

    def test_28_edit_payment(self):
        new_partner = self.env['res.partner'].create({'name': 'New Partner'})
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': new_partner.id,
            'amount': 500,
            'is_wallet': True,
            'wallet_amount': 500,
            'currency_id': self.env.company.currency_id.id,
            'wallet_type_id': self.consumption_wallet_type.id
        })
        self.assertRecordValues(payment.line_ids, [
            {
                'amount_currency': 500,
                'amount_residual_currency': 500,
                'wallet_amount_currency': 0,
                'wallet_amount_residual_currency': 0,
                'non_wallet_amount_currency': 500,
                'non_wallet_amount_residual_currency': 500,
            },
            {
                'amount_currency': -500,
                'amount_residual_currency': -500,
                'wallet_amount_currency': -500,
                'wallet_amount_residual_currency': -500,
                'non_wallet_amount_currency': 0,
                'non_wallet_amount_residual_currency': 0,
            }
        ])

        payment.is_wallet = False
        payment._onchange_wallet_amount()
        self.assertRecordValues(payment.line_ids, [
            {
                'amount_currency': 500,
                'amount_residual_currency': 500,
                'wallet_amount_currency': 0,
                'wallet_amount_residual_currency': 0,
                'non_wallet_amount_currency': 500,
                'non_wallet_amount_residual_currency': 500,
            },
            {
                'amount_currency': -500,
                'amount_residual_currency': -500,
                'wallet_amount_currency': 0,
                'wallet_amount_residual_currency': 0,
                'non_wallet_amount_currency': -500,
                'non_wallet_amount_residual_currency': -500,
            }
        ])

    def test_29_unreconcile_invoice(self):
        invoice = self.create_invoice(custom_line_vals_list=[{'price_unit': 100000}])
        payment = self.create_payment(
            amount=100000,
            wallet_amount=100000,
            is_wallet=True,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        wallet = payment.wallet_id
        self.assertEqual(wallet.amount, 100000)
        self.reconcile_payment_vs_invoice(payment, invoice)
        self.assertEqual(wallet.amount, 0)
        self.assertRecordValues(wallet.wallet_history_ids.sorted(lambda h: h.id), [{
            'currency_id': self.currency_usd.id,
            'amount': 100000,
            'wallet_history_type': 'top-up',
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }, {
            'currency_id': self.currency_usd.id,
            'amount': -100000,
            'wallet_history_type': 'payment',
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        invoice.button_draft()
        self.assertEqual(wallet.amount, 100000)
        self.assertRecordValues(wallet.wallet_history_ids.sorted(lambda h: h.id), [{
            'currency_id': self.currency_usd.id,
            'amount': 100000,
            'wallet_history_type': 'top-up',
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }, {
            'currency_id': self.currency_usd.id,
            'amount': -100000,
            'wallet_history_type': 'payment',
            'state': 'cancel',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.assertEqual(self.partner.commercial_partner_id.wallet_ids.amount, 100000)

    def test_30_unreconcile_invoice(self):
        invoice = self.create_invoice(custom_line_vals_list=[{'price_unit': 100000}])
        receivable_invoice_line = invoice.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        payment = self.create_payment(
            amount=100000,
            wallet_amount=100000,
            is_wallet=True,
            wallet_type_id=self.consumption_wallet_type.id,
        )
        receivable_payment_line = payment.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        wallet = payment.wallet_id
        self.assertEqual(wallet.amount, 100000)
        self.reconcile_payment_vs_invoice(payment, invoice)
        self.assertEqual(wallet.amount, 0)
        self.assertRecordValues(wallet.wallet_history_ids.sorted(lambda h: h.id), [{
            'currency_id': self.currency_usd.id,
            'amount': 100000,
            'wallet_history_type': 'top-up',
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }, {
            'currency_id': self.currency_usd.id,
            'amount': -100000,
            'wallet_history_type': 'payment',
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        (receivable_invoice_line | receivable_payment_line).remove_move_reconcile()
        self.assertEqual(wallet.amount, 100000)
        self.assertRecordValues(wallet.wallet_history_ids.sorted(lambda h: h.id), [{
            'currency_id': self.currency_usd.id,
            'amount': 100000,
            'wallet_history_type': 'top-up',
            'state': 'done',
            'wallet_type_id': self.consumption_wallet_type.id
        }, {
            'currency_id': self.currency_usd.id,
            'amount': -100000,
            'wallet_history_type': 'payment',
            'state': 'cancel',
            'wallet_type_id': self.consumption_wallet_type.id
        }])
        self.assertEqual(self.partner.commercial_partner_id.wallet_ids.amount, 100000)
