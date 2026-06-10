from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    wallet_id = fields.Many2one(comodel_name='wallet', string='Wallet', ondelete='restrict', copy=False)
    wallet_history_ids = fields.Many2many(comodel_name='wallet.history', string='Transaction Histories', copy=False)
    wallet_amount_currency = fields.Monetary(currency_field='currency_id')
    wallet_amount_residual_currency = fields.Monetary(
        currency_field='currency_id',
        compute='_compute_wallet_amount_residual_currency', store=True,
    )
    non_wallet_amount_currency = fields.Monetary(currency_field='currency_id', copy=True,
        compute='_compute_non_wallet_amount_currency', store=True,
    )
    non_wallet_amount_residual_currency = fields.Monetary(
        currency_field='currency_id',
        compute='_compute_non_wallet_amount_residual_currency', store=True,
    )

    @api.constrains('wallet_id', 'wallet_history_ids')
    def _check_wallet_history(self):
        for r in self:
            if r.wallet_id and r.wallet_history_ids and r.wallet_history_ids.filtered(lambda h: h.state != 'cancel' and h.wallet_id != r.wallet_id):
                raise ValidationError(_("A journal item can only link to transaction histories within the same wallet!"))

    @api.depends(
        'matched_debit_ids',
        'matched_debit_ids.wallet_amount_currency',
        'wallet_amount_currency'
    )
    def _compute_wallet_amount_residual_currency(self):
        skip_wallet_residual_lines = self.filtered(lambda r: r.currency_id.is_zero(r.wallet_amount_currency))
        skip_wallet_residual_lines.wallet_amount_residual_currency = 0
        for aml in (self - skip_wallet_residual_lines):
            wallet_amount_matched = sum((aml.matched_debit_ids | aml.matched_credit_ids).mapped('wallet_amount_currency'))
            sign = 1 if aml.wallet_amount_currency > 0 else -1
            aml.wallet_amount_residual_currency = sign * (abs(aml.wallet_amount_currency) - abs(wallet_amount_matched))

    @api.depends(
        'amount_residual_currency',
        'wallet_amount_residual_currency'
    )
    def _compute_non_wallet_amount_residual_currency(self):
        for aml in self:
            aml.non_wallet_amount_residual_currency = aml.amount_residual_currency - aml.wallet_amount_residual_currency

    @api.depends('amount_currency', 'wallet_amount_currency')
    def _compute_non_wallet_amount_currency(self):
        for aml in self:
            aml.non_wallet_amount_currency = aml.amount_currency - aml.wallet_amount_currency

    def action_register_payment_by_wallet(self):
        ''' Open the wallet.payment.wizard to pay the selected journal items.
        :return: An action opening the wallet.payment.wizard.
        '''
        return {
            'name': _('Register Payment By Wallet'),
            'res_model': 'wallet.payment.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'context': {
                'active_model': 'account.move.line',
                'active_ids': self.ids,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    def reconcile(self):
        results = super(AccountMoveLine, self).reconcile()
        self._handle_partial_after_reconcile()
        return results

    @api.model
    def _handle_partial_after_reconcile(self):
        """
        * We determine that depositing money into the wallet will credit the customer's receivable account,
        whereas withdrawing or spending money from the wallet will debit the customer's receivable account.
        Therefore, wallet-related reconciliation operations will only be performed when the journal items on
        the debit side and the credit side of the customer account receivable are always in the same currency.

        #Step 1: Check before handle:
            E.g: Account receivable is 131 - Customer Receivable
            => Reconcile is blocked if:
                * Debit 131 (VND) - (Customer Invoice) <=> Credit 131 (USD) - (Top Up Wallet)
            => Reconcile is passed if:
                * Debit 131 (VND) - (Customer Invoice) <=> Credit 131 (VND) - (Top Up Wallet)
                * Debit 131 (USD) - (Customer Invoice) <=> Credit 131 (VND) - (Customer Payment)

        #Step 2: Calculate wallet amount currency matched:
            => Details have been described in method `_partial_update_wallet_amount_currency_matched()`

        #Step 3: Create a wallet transaction history based on the matched wallet currency amount:
            => Details have been described in method `_partial_deduct_wallet_balance()`

        """
        partials = (self.matched_debit_ids | self.matched_credit_ids).filtered(lambda p: p.credit_currency_id.is_zero(p.wallet_amount_currency))
        partials_todo = partials.filtered(lambda p: p._is_wallet_partial())
        if partials_todo.filtered(lambda p: p.credit_currency_id != p.debit_currency_id):
            raise ValidationError(
                _("Could not reconcile journal items related to wallet transactions in different currencies!")
            )
        partials_todo._partial_update_wallet_amount_currency_matched()
        partials_todo._partial_deduct_wallet_balance()

    def _is_receivable_wallet_line(self):
        self.ensure_one()
        return self.partner_id \
            and self.account_type == 'asset_receivable' \
            and (self.wallet_id or self.wallet_history_ids)
