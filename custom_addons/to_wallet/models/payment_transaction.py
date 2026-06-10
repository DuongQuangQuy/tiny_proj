from werkzeug import urls

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError
from odoo.addons.payment import utils as payment_utils


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    wallet_id = fields.Many2one('wallet', string='Wallet', readonly=True)
    wallet_history_ids = fields.One2many(
        comodel_name='wallet.history', inverse_name='payment_transaction_id',
        string='Wallet Transaction Histories', readonly=True)

    @api.model
    def _compute_reference(self, provider_code, prefix=None, separator='-', **kwargs):
        """ Override of `payment` to ensure that APS' requirements for references are satisfied.

        APS' requirements for transaction are as follows:
        - References can only be made of alphanumeric characters and/or '-' and '_'.
          The prefix is generated with 'tx' as default. This prevents the prefix from being
          generated based on document names that may contain non-allowed characters
          (eg: INV/2020/...).

        :param str provider_code: The code of the provider handling the transaction.
        :param str prefix: The custom prefix used to compute the full reference.
        :param str separator: The custom separator used to separate the prefix from the suffix.
        :return: The unique reference for the transaction.
        :rtype: str
        """
        if provider_code == 'wallet':
            prefix = payment_utils.singularize_reference_prefix(prefix='WALLET/PAYMENT', separator='/')

        return super()._compute_reference(provider_code, prefix=prefix, separator=separator, **kwargs)

    def _prepare_wallet_payment(self):
        self.ensure_one()
        return {
            'is_wallet': True,
            'wallet_type_id': self.wallet_id.wallet_type_id.id,
            'wallet_amount': abs(self.amount),  # A tx may have a negative amount, but a payment must >= 0
        }

    def _create_payment(self, **extra_create_values):
        if self.wallet_id:
            if self.sudo().provider_id.code == 'wallet':
                return self.env['account.payment']
            if extra_create_values is None:
                extra_create_values = {}
            extra_create_values.update(self._prepare_wallet_payment())
        return super(PaymentTransaction, self)._create_payment(**extra_create_values)

    def _create_wallet_payment_history(self, amount=None, force_done=True, **extra_value):
        self.ensure_one()
        if not self.wallet_id:
            raise ValidationError(_("No wallet linked to the specified payment transaction was found!"))
        return self.wallet_id._create_wallet_history(
            amount=amount or -self.amount,
            history_type='payment',
            force_done=force_done,
            payment_transaction_id=self.id,
            **extra_value
        )

    def _reconcile_after_done(self):
        skip_txs = self.env['payment.transaction']
        context = {
            'force_pay_by_wallet': True,
            'skip_creating_wallet_history': self.env.context.get('skip_creating_wallet_history', {})
        }
        for tx in self:
            wallet = tx.wallet_id
            if tx.sudo().provider_id.code == 'wallet' and wallet:
                tx_amount = tx.amount
                wallet_histories = tx.wallet_history_ids.filtered(lambda h: h.state != 'cancel')
                if tx.currency_id.compare_amounts(tx_amount - abs(sum(wallet_histories.mapped('amount'))), wallet.amount) > 0:
                    msg = _("Wallet balance is unavailable! (Remaining balance: %s)") % (wallet.currency_id.format(wallet.amount))
                    tx._set_error(state_message=msg)
                    continue
                invoices = tx.invoice_ids
                if not invoices:
                    tx._create_wallet_payment_history()
                    continue
                for invoice in invoices:
                    # On the invoice there is only one line with account type 'asset_receivable'
                    receivable_line = invoice.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
                    amount = -1 * receivable_line.amount_residual_currency
                    wallet_history = tx._create_wallet_payment_history(amount=amount, account_move_line_ids=[(4, receivable_line.id)])
                    context['skip_creating_wallet_history'][receivable_line.id] = wallet_history.ids
                    # Validate invoices and reconcile invoices with wallet once the transaction is confirmed
                    invoice.filtered(lambda inv: inv.state == 'draft').with_context(**context).action_post()
                    # Make sure the data in the cache is identical to the data edited after calling `action_post()`
                    receivable_line.invalidate_recordset(['reconciled'])
                    if not receivable_line.reconciled:
                        tx.wallet_id.with_context(**context)._reconcile_wallet(receivable_line)
                skip_txs |= tx
        return super(PaymentTransaction, self - skip_txs)._reconcile_after_done()

    def _process_notification_data(self, notification_data):
        """ Override of payment to process the transaction based on dummy data.

        Note: self.ensure_one()

        :param dict notification_data: The dummy notification data
        :return: None
        :raise: ValidationError if inconsistent data were received
        """
        if self.provider_code != 'wallet':
            return super()._process_notification_data(notification_data)

        update_vals = {}
        if not self.wallet_id:
            wallet_id = notification_data.get('wallet_id', False)
            if not wallet_id:
                raise ValidationError(_('E-Wallet: Unable to identify transaction wallet!'))
            update_vals['wallet_id'] = wallet_id
        update_vals['provider_reference'] = payment_utils.singularize_reference_prefix(prefix='WALLET/PAYMENT', separator='/')
        self.write(update_vals)
        self._set_done()

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of payment to find the transaction based on payment data.

        :param str provider_code: The code of the provider that handled the transaction
        :param dict notification_data: The payment notification data
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if the data match no transaction
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'wallet':
            return tx

        reference = notification_data.get('reference')
        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'wallet')])
        if not tx:
            raise ValidationError(
                _("E-Wallet: No transaction found matching reference %s.", reference)
            )
        return tx

    @api.model
    def genarate_payment_link_top_up_or_withdraw_wallet(self, wallet_id, amount, wallet_operation='top-up'):
        wallet_id = int(wallet_id)
        amount = float(amount)
        if wallet_id:
            wallet_sudo = self.env['wallet'].sudo().browse(wallet_id).exists()
        base_url = self.get_base_url()  # Don't generate links for the wrong website
        currency = wallet_sudo.currency_id
        reference_prefix = f'WALLET/{wallet_operation.upper()}'
        url_params = {
            'reference': payment_utils.singularize_reference_prefix(prefix=reference_prefix, separator='/'),
            'amount': amount,
            'access_token': payment_utils.generate_access_token(wallet_sudo.partner_id.id, amount, currency.id),
            'wallet_id': wallet_id,
        }
        if wallet_operation == 'top-up':
            return f'{base_url}/payment/pay?{urls.url_encode(url_params)}'
        if wallet_operation == 'withdraw':
            return f'{base_url}/my/wallets/withdraw?{urls.url_encode(url_params)}'
        return f'{base_url}/my/wallets'

    def _set_pending(self, state_message=None, extra_allowed_states=()):
        super(PaymentTransaction, self)._set_pending(state_message=state_message, extra_allowed_states=extra_allowed_states)
        for tx in self:
            wallet = tx.wallet_id
            # Create pending wallet history to schedule verification to backend users
            if wallet and tx.provider_id.code != 'wallet':
                wallet._create_wallet_history(
                    amount=tx.amount,
                    history_type='top-up',
                    payment_transaction_id=self.id,
                )
