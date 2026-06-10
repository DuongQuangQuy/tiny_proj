from odoo import fields, models, _
from odoo.tools.float_utils import float_compare
from odoo.exceptions import ValidationError


class AccountPartialReconcile(models.Model):
    _inherit = 'account.partial.reconcile'

    wallet_id = fields.Many2one('wallet', string='Wallet')
    wallet_amount_currency = fields.Monetary(
        currency_field='credit_currency_id',
        help="Always positive amount concerned by this matching expressed "
        "in the wallet credit/debit line foreign currency."
    )
    wallet_history_id = fields.Many2one('wallet.history', string='Wallet History')

    def unlink(self):
        # Because self is a set of records that may contain the same id because
        # the function `remove_move_reconcile()` uses the operator to add two recordsets.
        # For example: account.partial.reconcile(1, 1, 2)
        for partial in self.browse(set(self.ids)).with_prefetch(self.ids):
            if partial.wallet_id and partial._is_wallet_partial():
                wallet_history = partial.wallet_history_id
                partial.debit_move_id.wallet_history_ids = [(3, wallet_history.id)]
                wallet_history.action_cancel()
        return super(AccountPartialReconcile, self).unlink()

    def _is_exchange_partial(self):
        self.ensure_one()
        return (self.credit_move_id | self.debit_move_id).move_id.filtered(
            lambda m: m.journal_id == self.company_id.currency_exchange_journal_id)

    def _is_wallet_partial(self):
        self.ensure_one()
        return self.credit_move_id._is_receivable_wallet_line() \
            and self.credit_move_id.account_type == 'asset_receivable' \
            and not self._is_exchange_partial()

    def _partial_update_wallet_amount_currency_matched(self):
        """
            E.g: Customer makes a one-time payment of 200 USD, in there:
                * 150 USD to pay for purchased products and services (A)
                * 50 USD to top up the wallet (B)
            There will be 2 cases of reconciliation: Amount (A) is used first or Amount (B) is used first.

            => Case amount (A) is used first a wallet transaction history is only generated when
            the payment amount exceeds the 150 USD mark:
                * The customer's invoice for products and services has a total value of 170 USD.
                When the customer requests payment, the amount is deducted from the outstanding
                credit will be 150 USD from (A) and 20 USD from (B). If the total bill is only 140 USD,
                the amount is deducted from the outstanding credit will be 140 USD from (B) and no
                wallet transaction history will be created.

            => Case Amount (B) is used first a wallet transaction history will be generated:
                * The customer's purchase invoice for products and services has a total value of 40 USD.
                When a customer requests payment using the wallet, the amount is deducted from the outstanding
                credit of 40 USD (B) and a transaction history is created on the wallet.
        """
        for partial in self:
            # Ignore if partial reconciliation is not a wallet transaction matching process
            if not partial._is_wallet_partial():
                continue
            # Prepare parameters for calculation
            cr_wallet_aml = partial.credit_move_id
            credit_amount_currency = partial.credit_amount_currency
            wallet_amount_currency = abs(cr_wallet_aml.wallet_amount_currency)
            wallet_transaction_amount = 0
            # Calculate wallet amount currency matched
            if self.env.context.get('force_pay_by_wallet', False) and not self.env.context.get('payment_residual_as_top_up', False):
                compare_result = cr_wallet_aml.currency_id.compare_amounts(wallet_amount_currency, credit_amount_currency) > 0
                wallet_transaction_amount = credit_amount_currency if compare_result else wallet_amount_currency
            else:
                non_wallet_amount_currency = abs(cr_wallet_aml.non_wallet_amount_currency)
                amount_currency_matched = abs(cr_wallet_aml.amount_currency - cr_wallet_aml.amount_residual_currency)
                if partial.debit_currency_id.compare_amounts(amount_currency_matched, non_wallet_amount_currency) > 0:
                    wallet_amount_currency_matched = wallet_amount_currency - abs(cr_wallet_aml.wallet_amount_residual_currency)
                    wallet_transaction_amount = (amount_currency_matched - non_wallet_amount_currency - wallet_amount_currency_matched)
            # Update calculated results
            partial.wallet_amount_currency = wallet_transaction_amount
            partial.debit_move_id.wallet_amount_currency += wallet_transaction_amount
            if float_compare(wallet_transaction_amount, 0, precision_rounding=cr_wallet_aml.currency_id.rounding or 0.01) > 0:
                partial.wallet_id = cr_wallet_aml.wallet_id

    def _partial_deduct_wallet_balance(self):
        context = self.env.context
        # Context `skip_creating_wallet_history` is used to bypass the wallet history generation and instead link the
        # wallet history in context to the matched reconcile document of journal items. this context has the format
        # is a dictionary {account.move.line(1).id: [wallet.history(1).id]}
        skip_creating_wallet_history = context.get('skip_creating_wallet_history', {})
        # Context `default_wallet_history_type` is used to mark the expected wallet transaction history type for
        # initializing the transaction history when reconciling wallet-related journal items takes place.
        default_wallet_history_type = context.get('default_wallet_history_type', False)
        for partial in self:
            # Check before create wallet transaction history
            if not partial._is_wallet_partial():
                raise ValidationError(
                    _("Unable to create wallet transaction history for partial reconciliation not related to wallet!")
                )
            db_wallet_aml = partial.debit_move_id
            wallet_amount_currency_matched = partial.wallet_amount_currency
            if partial.debit_currency_id.compare_amounts(wallet_amount_currency_matched, 0) <= 0:
                continue
            wallet_history = self.env['wallet.history'].browse(skip_creating_wallet_history.get(db_wallet_aml.id, [])).exists()
            if wallet_history and wallet_history.wallet_id == partial.wallet_id:
                # Update wallet history for matched reconcile
                partial.write({'wallet_history_id': wallet_history.id})
                continue
            # Create wallet transaction history
            payment = db_wallet_aml.payment_id
            partial.wallet_history_id = partial.wallet_id._create_wallet_history(
                amount=-1 * wallet_amount_currency_matched,
                history_type='withdraw' if payment and payment.is_wallet and payment.payment_type == 'outbound' else (default_wallet_history_type or 'payment'),
                force_done=True,
                account_move_line_ids=[(4, db_wallet_aml.id)]
            )
