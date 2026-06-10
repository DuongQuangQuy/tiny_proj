from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError, AccessError
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.controllers.portal import PaymentPortal


class WalletPaymentPortal(PaymentPortal):

    @http.route()
    def payment_pay(self, *args, amount=None, wallet_id=None, access_token=None, **kwargs):
        """ Override of `payment` to replace the missing transaction values by that of the wallet top-up.

        This is necessary for the reconciliation as all transaction values, excepted the amount,
        need to match exactly that of the wallet.

        :param str amount: The (possibly partial) amount to pay used to check the access token.
        :param str wallet_id: The wallet for which a payment id made, as an `wallet` id.
        :param str access_token: The access token used to authenticate the partner.
        :return: The result of the parent method.
        :rtype: str
        :raise ValidationError: If the wallet id is invalid.
        """
        # Cast numeric parameters as int or float and void them if their str value is malformed.
        amount = self._cast_as_float(amount)
        wallet_id = self._cast_as_int(wallet_id)
        if wallet_id:
            wallet_sudo = request.env['wallet'].sudo().browse(wallet_id).exists()
            if not wallet_sudo:
                raise ValidationError(_("The provided parameters are invalid."))

            # Check the access token against the top up wallet values. Done after fetching the wallet
            # as we need the wallet fields to check the access token.
            if not payment_utils.check_access_token(
                access_token, wallet_sudo.partner_id.id, amount, wallet_sudo.currency_id.id
            ):
                raise ValidationError(_("The provided parameters are invalid."))

            kwargs.update({
                'currency_id': wallet_sudo.currency_id.id,
                'partner_id': wallet_sudo.partner_id.id,
                'company_id': wallet_sudo.company_id.id,
                'wallet_id': wallet_sudo.id,
                'exclude_wallet_provider': True
            })
        return super().payment_pay(*args, amount=amount, access_token=access_token, **kwargs)

    def _get_extra_payment_form_values(self, wallet_id=None, access_token=None, **kwargs):
        form_values = super()._get_extra_payment_form_values(wallet_id=wallet_id, access_token=access_token, **kwargs)
        if wallet_id:
            wallet_id = self._cast_as_int(wallet_id)
            try:  # Check document access against what could be a portal access token.
                self._document_check_access('wallet', wallet_id)
            except AccessError:  # It is a payment access token computed on the payment context.
                if not payment_utils.check_access_token(
                    access_token,
                    kwargs.get('partner_id'),
                    kwargs.get('amount'),
                    kwargs.get('currency_id'),
                ):
                    raise
            form_values['wallet_id'] = wallet_id
        return form_values

    def _create_transaction(self, *args, custom_create_values=None, **kwargs):
        """ Override of `payment` to add the wallet id in the custom create values.

        :param int wallet_id: The wallet for which a payment id made, as an `wallet` id.
        :param dict custom_create_values: Additional create values overwriting the default ones.
        :param dict kwargs: Optional data. This parameter is not used here.
        :return: The result of the parent method.
        :rtype: recordset of `payment.transaction`
        """
        if 'wallet_id' in kwargs:
            if custom_create_values is None:
                custom_create_values = {}
            custom_create_values['wallet_id'] = kwargs.pop('wallet_id')
        return super(WalletPaymentPortal, self)._create_transaction(*args, custom_create_values=custom_create_values, **kwargs)

    @staticmethod
    def _validate_transaction_kwargs(kwargs, additional_allowed_keys=()):
        """ Verify that the keys of a transaction route's kwargs are all whitelisted.

        The whitelist consists of all the keys that are expected to be passed to a transaction
        route, plus optional contextually allowed keys.

        This method must be called in all transaction routes to ensure that no undesired kwarg can
        be passed as param and then injected in the create values of the transaction.

        :param dict kwargs: The transaction route's kwargs to verify.
        :param tuple additional_allowed_keys: The keys of kwargs that are contextually allowed.
        :return: None
        :raise ValidationError: If some kwargs keys are rejected.
        """
        cls = WalletPaymentPortal
        if 'wallet_id' in kwargs:
            additional_allowed_keys += ('wallet_id', )
        super(WalletPaymentPortal, cls)._validate_transaction_kwargs(kwargs, additional_allowed_keys)

    def _verify_notification_data(self, **data):
        return {
            'wallet_id': data.get('wallet_id', False),
            'reference': data.get('reference', ''),
        }

    @http.route('/my/wallets/payment/status', type='jsonrpc', auth='user')
    def wallet_payment_status(self, **data):
        """ Simulate the response of a payment request.

        :param dict data: The simulated notification data.
        :return: None
        """
        notification_data = self._verify_notification_data(**data)
        request.env['payment.transaction'].sudo()._handle_notification_data('wallet', notification_data)
