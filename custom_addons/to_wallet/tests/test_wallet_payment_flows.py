from freezegun import freeze_time
from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.addons.to_wallet.tests.common import TestWalletCommon
from odoo.addons.payment.tests.http_common import PaymentHttpCommon


@tagged('post_install', '-at_install')
class TestWalletPaymentFlows(TestWalletCommon, PaymentHttpCommon):

    def _portal_withdraw_wallet(self, **route_kwargs):
        """/my/wallets/withdraw txContext feedback

        NOTE: must be authenticated before calling method.
        Or an access_token should be specified in route_kwargs
        """
        uri = '/my/wallets/withdraw'
        url = self._build_url(uri)
        return self._make_http_get_request(url, route_kwargs)

    def _test_top_up_wallet(self, amount=10.0, wallet=None):
        wallet = wallet or self.portal_user_wallet
        wallet_balance = wallet.amount
        route_values = self._prepare_pay_values(amount=amount, currency=wallet.currency_id, partner=wallet.partner_id)
        route_values['wallet_id'] = wallet.id
        tx_context = self._get_portal_pay_context(**route_values)
        # /payment/transaction
        tx_route_values = {
            'provider_id': self.provider.id,
            'payment_method_id': self.payment_method_id,
            'token_id': None,
            'amount': tx_context['amount'],
            'currency_id': route_values['currency_id'],
            'partner_id': route_values['partner_id'],
            'wallet_id': route_values['wallet_id'],
            'flow': 'direct',
            'tokenization_requested': False,
            'landing_route': tx_context['landing_route'],
            'access_token': tx_context['access_token'],
        }
        with mute_logger('odoo.addons.payment.models.payment_transaction'):
            processing_values = self._get_processing_values(tx_route=tx_context['transaction_route'], **tx_route_values)
        tx_sudo = self._get_tx(processing_values['reference'])
        self.assertFalse(tx_sudo.payment_id)
        tx_sudo._set_done()
        tx_sudo._finalize_post_processing()
        self.assertRecordValues(
            tx_sudo.payment_id,
            [
                {
                    'partner_id': wallet.partner_id.id,
                    'amount': amount,
                    'is_wallet': True,
                    'wallet_id': wallet.id,
                    'wallet_amount': amount,
                    'currency_id': wallet.currency_id.id,
                    'state': 'posted',
                    'payment_type': 'inbound'
                }
            ]
        )
        self.assertRecordValues(
            tx_sudo.payment_id.line_ids.wallet_history_ids,
            [
                {
                    'wallet_id': wallet.id,
                    'amount': amount,
                    'currency_id': wallet.currency_id.id,
                    'state': 'done',
                }
            ]
        )
        self.assertEqual(wallet.amount, wallet_balance + amount)

    def _test_withdraw_wallet(self, amount=10.0, wallet=None):
        wallet = wallet or self.portal_user_wallet
        wallet_balance = wallet.amount
        route_values = self._prepare_pay_values(amount=amount, currency=wallet.currency_id, partner=wallet.partner_id)
        route_values['wallet_id'] = wallet.id
        response = self._portal_withdraw_wallet(**route_values)
        self.assertEqual(response.status_code, 200)
        payment = self.env['account.payment'].search([('ref', '=', route_values['reference'])])
        payment.action_post()
        self.assertRecordValues(
            payment,
            [
                {
                    'partner_id': wallet.partner_id.id,
                    'amount': amount,
                    'is_wallet': True,
                    'wallet_id': wallet.id,
                    'wallet_amount': amount,
                    'currency_id': wallet.currency_id.id,
                    'state': 'posted',
                    'payment_type': 'outbound'
                }
            ]
        )
        self.assertRecordValues(
            payment.line_ids.wallet_history_ids,
            [
                {
                    'wallet_id': wallet.id,
                    'amount': -amount,
                    'currency_id': wallet.currency_id.id,
                    'state': 'done',
                }
            ]
        )
        self.assertEqual(wallet.amount, wallet_balance - amount)

    @freeze_time('2023-11-01 00:00:00')
    def test_01_wallet_payment_flow(self):
        """Test the payment of top-up/withdraw wallet through the payment/pay route"""

        # Login portal user
        self.authenticate(self.portal_user.login, 'newportaluser')

        # Check available balance before top up
        self.assertRecordValues(self.portal_user_wallet, [
            {
                'partner_id': self.portal_user.partner_id.id,
                'wallet_type_id': self.wallet_type.id,
                'amount': 0.0,
                'amount_pending': 0.0,
                'currency_id': self.currency_usd.id,
            }
        ])

        # ==================================================
        # Top up $10 to wallet
        # ==================================================

        self._test_top_up_wallet()

        # ==================================================
        # Withdraw $5 from wallet
        # ==================================================

        self._test_withdraw_wallet(amount=5.0)

        # ==================================================
        # Pay invoice $5 by wallet
        # ==================================================

        # Pay for this invoice (no impact even if amounts do not match)
        invoice = self.create_invoice(
            custom_vals={
                'currency_id': self.currency_usd.id,
                'partner_id': self.portal_user.partner_id.id
            },
            custom_line_vals_list=[{'price_unit': 5}]
        )
        route_values = self._prepare_pay_values(
            amount=5.0,
            currency=invoice.currency_id,
            reference=invoice.name,
            partner=invoice.partner_id
        )
        route_values['invoice_id'] = invoice.id
        tx_context = self._get_portal_pay_context(**route_values)

        # invoice/transaction
        tx_route_values = {
            'provider_id': self.wallet_provider.id,
            'payment_method_id': self.wallet_payment_method.id,
            'wallet_id': self.portal_user_wallet.id,
            'token_id': None,
            'amount': tx_context['amount'],
            'flow': 'direct',
            'tokenization_requested': False,
            'landing_route': tx_context['landing_route'],
            'access_token': tx_context['access_token'],
        }
        with mute_logger('odoo.addons.payment.models.payment_transaction'):
            processing_values = self._get_processing_values(
                tx_route=tx_context['transaction_route'], **tx_route_values
            )
        tx_sudo = self._get_tx(processing_values['reference'])
        self.assertRecordValues(
            tx_sudo,
            [
                {
                    'partner_id': self.portal_user.partner_id.id,
                    'wallet_id': self.portal_user_wallet.id,
                    'amount': 5.0,
                    'currency_id': self.currency_usd.id,
                    'provider_id': self.wallet_provider.id,
                    'state': 'draft',
                    'wallet_history_ids': []
                }
            ]
        )
        tx_sudo._set_done()
        tx_sudo._finalize_post_processing()
        self.assertEqual(tx_sudo.state, 'done')
        self.assertFalse(tx_sudo.payment_id)
        self.assertRecordValues(
            invoice.line_ids.wallet_history_ids,
            [
                {
                    'wallet_id': self.portal_user_wallet.id,
                    'amount': -5.0,
                    'currency_id': self.currency_usd.id,
                    'state': 'done',
                }
            ]
        )
        # Check available balance after pay invoice
        self.assertRecordValues(self.portal_user_wallet, [
            {
                'partner_id': self.portal_user.partner_id.id,
                'wallet_type_id': self.wallet_type.id,
                'amount': 0.0,
                'amount_pending': 0.0,
                'currency_id': self.currency_usd.id,
            }
        ])

    @freeze_time('2023-11-01 00:00:00')
    def test_02_wallet_payment_flow(self):
        """Test the payment of top-up/withdraw wallet through the payment/pay route"""

        # Login portal user
        self.authenticate(self.portal_user.login, 'newportaluser')

        # Check available balance before top up
        self.assertRecordValues(self.portal_user_wallet, [
            {
                'partner_id': self.portal_user.partner_id.id,
                'wallet_type_id': self.wallet_type.id,
                'amount': 0.0,
                'amount_pending': 0.0,
                'currency_id': self.currency_usd.id,
            }
        ])

        # ==================================================
        # Top up $20 to wallet
        # ==================================================

        self._test_top_up_wallet(amount=20.0)

        # Check available balance after top up
        self.assertRecordValues(self.portal_user_wallet, [
            {
                'partner_id': self.portal_user.partner_id.id,
                'wallet_type_id': self.wallet_type.id,
                'amount': 20.0,
                'amount_pending': 0.0,
                'currency_id': self.currency_usd.id,
            }
        ])

        # ==================================================
        # Pay invoice $20 by wallet
        # ==================================================

        # Pay for this invoice (no impact even if amounts do not match)
        invoice = self.create_invoice(
            custom_vals={
                'currency_id': self.currency_usd.id,
                'partner_id': self.portal_user.partner_id.id
            },
            custom_line_vals_list=[{'price_unit': 20}]
        )
        route_values = self._prepare_pay_values(
            amount=20.0,
            currency=self.currency_usd,
            reference=invoice.name,
            partner=self.portal_user.partner_id
        )
        route_values['invoice_id'] = invoice.id
        tx_context = self._get_portal_pay_context(**route_values)

        # invoice/transaction
        tx_route_values = {
            'provider_id': self.wallet_provider.id,
            'payment_method_id': self.wallet_payment_method.id,
            'wallet_id': self.portal_user_wallet.id,
            'token_id': None,
            'amount': tx_context['amount'],
            'flow': 'direct',
            'tokenization_requested': False,
            'landing_route': tx_context['landing_route'],
            'access_token': tx_context['access_token'],
        }
        with mute_logger('odoo.addons.payment.models.payment_transaction'):
            processing_values = self._get_processing_values(
                tx_route=tx_context['transaction_route'], **tx_route_values
            )
        tx_sudo = self._get_tx(processing_values['reference'])
        self.assertRecordValues(
            tx_sudo,
            [
                {
                    'partner_id': self.portal_user.partner_id.id,
                    'wallet_id': self.portal_user_wallet.id,
                    'amount': 20.0,
                    'currency_id': self.currency_usd.id,
                    'provider_id': self.wallet_provider.id,
                    'state': 'draft',
                    'wallet_history_ids': []
                }
            ]
        )
        tx_sudo._set_done()
        tx_sudo._finalize_post_processing()
        self.assertEqual(tx_sudo.state, 'done')
        self.assertFalse(tx_sudo.payment_id)
        self.assertRecordValues(
            invoice.line_ids.wallet_history_ids,
            [
                {
                    'wallet_id': self.portal_user_wallet.id,
                    'amount': -20.0,
                    'currency_id': self.currency_usd.id,
                    'state': 'done',
                }
            ]
        )
        # Check available balance after pay invoice
        self.assertRecordValues(self.portal_user_wallet, [
            {
                'partner_id': self.portal_user.partner_id.id,
                'wallet_type_id': self.wallet_type.id,
                'amount': 0.0,
                'amount_pending': 0.0,
                'currency_id': self.currency_usd.id,
            }
        ])
