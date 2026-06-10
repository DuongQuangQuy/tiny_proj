from odoo import models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def button_draft(self):
        res = super(AccountMove, self).button_draft()
        receivable_wallet_lines = self._get_receivable_wallet_lines()
        if receivable_wallet_lines:
            raise ValidationError(
                _("Journal entries related to transactions in the customer's e-wallet cannot be reset to draft after being posted.")
            )
        return res

    def _get_receivable_wallet_lines(self):
        """
        This method get all the receivable move lines of the invoices in self that are wallet operations related
        """
        return self.line_ids.filtered(lambda l: l._is_receivable_wallet_line())

    def _has_transaction_paid_by_wallet(self):
        self.ensure_one()
        if not self.transaction_ids:
            return False
        return any([tx.provider_id.code == 'wallet' and tx.wallet_id for tx in self.transaction_ids.sudo()])

    def _post(self, soft=True):
        """
        * Auto-reconcile the invoice with wallet coming from transactions. It's useful when you have a "paid"
        sale order (using a payment transaction) and you invoice it later.

        * For money entering the wallet, always credit the customer's receivable account.
        On the contrary, for money coming out of the wallet, always debit the customer's receivable account.

        * Thus, if a customer top up money into the wallet or get money from loyalty programs, affiliate programs,... ,
        the wallet transaction history will be created immediately. If the customer withdraws wallet money or uses wallet
        money to pay for products or services, the system will not create a transaction history immediately but will through
        reconciliation of journal entries to create wallet transaction history (processed by reconcile() function in account.move.line)
        """
        skip_creating_wallet_history = self.env.context.get('skip_creating_wallet_history', {})
        for move in self.filtered(lambda m: m._has_transaction_paid_by_wallet()):
            # On the invoice there is only one line with account type 'asset_receivable'
            receivable_invoice_line = move.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
            for tx in move.transaction_ids.sudo().filtered(lambda t: t.provider_id.code == 'wallet' and t.wallet_id):
                wallet_hisories = tx.wallet_history_ids.filtered(lambda h: not h.account_move_line_ids and h.state != 'cancel')
                if not wallet_hisories: continue
                receivable_invoice_line.write({
                    'wallet_id': tx.wallet_id.id,
                    'wallet_history_ids': [(4, h.id) for h in wallet_hisories]
                })
                skip_creating_wallet_history[receivable_invoice_line.id] = wallet_hisories.ids
        self = self.with_context(skip_creating_wallet_history=skip_creating_wallet_history)
        res = super(AccountMove, self)._post(soft)

        receivable_lines = self._get_receivable_wallet_lines()
        credit_receivable_lines = receivable_lines.filtered(lambda l: l.credit > 0)

        debit_receivable_lines = receivable_lines - credit_receivable_lines

        if credit_receivable_lines:
            credit_receivable_lines.move_id._add_wallet_balance()  # top up, loyalty programs, affiliate programs, ...
        if debit_receivable_lines:
            debit_receivable_lines.move_id._deduct_wallet_balance()  # withdraw, uses wallet money to pay for products or services.
        return res

    def _add_wallet_balance(self, history_type='top-up'):
        wallet_histories = self.env['wallet.history']
        skip_creating_wallet_history = self.env.context.get('skip_creating_wallet_history', {})
        receivable_wallet_lines = self._get_receivable_wallet_lines()
        credit_receivable_wallet_lines = receivable_wallet_lines.filtered(lambda l: l.credit > 0 and not l.reconciled)
        for line in credit_receivable_wallet_lines:
            wallet_histories_created = self.env['wallet.history'].browse(skip_creating_wallet_history.get(line.id, [])).exists()
            if wallet_histories_created:
                wallet_histories |= wallet_histories_created
            if not wallet_histories_created and line.partner_id and line.currency_id.compare_amounts(abs(line.wallet_amount_currency), 0) > 0:
                wallet_history = line.wallet_id._create_wallet_history(
                    amount=abs(line.wallet_amount_currency),
                    history_type=history_type,
                    force_done=True,
                    account_move_line_ids=[(4, line.id)]
                )
                line.payment_id.memo = wallet_history.reference
                wallet_histories |= wallet_history
        return wallet_histories

    def _deduct_wallet_balance(self):
        """ Create wallet transaction history processed by reconcile() function in 'account.move.line' """
        receivable_wallet_lines = self._get_receivable_wallet_lines()
        debit_receivable_wallet_lines = receivable_wallet_lines.filtered(lambda l: l.debit > 0 and not l.reconciled)
        for wallet in debit_receivable_wallet_lines.wallet_id:
            grouped_lines = debit_receivable_wallet_lines.filtered(lambda l: l.wallet_id == wallet)
            wallet.with_context(force_pay_by_wallet=True)._reconcile_wallet(grouped_lines)

    def action_register_payment_by_wallet(self):
        move_lines = self.line_ids.filtered(
            lambda l: l.move_id.state == 'posted'
            and l.account_id.account_type in ['asset_receivable', 'liability_payable']
            and not l.reconciled
        )
        return move_lines.action_register_payment_by_wallet()
