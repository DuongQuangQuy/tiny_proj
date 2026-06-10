from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_wallet = fields.Boolean(
        string='Is Top Up/Withdraw Wallet', compute='_compute_is_wallet', store=True, readonly=False, copy=False,
        help="Check this field if the payment is top up/withdraw from wallet."
    )
    wallet_amount = fields.Monetary(
        string='Amount Top Up Wallet', copy=False,
        help="Amount top up wallet through payments."
    )
    wallet_type_id = fields.Many2one(
        comodel_name='wallet.type', string='Wallet Type', copy=False,
    )
    wallet_id = fields.Many2one(
        comodel_name='wallet', string='Wallet', copy=False,
        help="The related wallet of the payment."
    )

    @api.constrains('payment_type', 'is_wallet')
    def _check_payment_type(self):
        for r in self:
            if r.is_wallet and r.payment_type not in ('inbound', 'outbound'):
                raise ValidationError(_('Only use send/receive payment type can top up/withdraw with wallet!'))

    @api.constrains('amount', 'wallet_amount', 'journal_id')
    def _check_wallet_amount_vs_amount(self):
        description = {'inbound': _("Wallet top up amount"), 'outbound': _("Wallet withdraw amount")}
        for r in self:
            currency = r.currency_id or r.journal_id.currency_id or r.company_id.currency_id
            if float_compare(r.wallet_amount, 0.0, precision_rounding=currency.rounding) == -1:
                raise ValidationError(_("%s must be greater or equal to 0") % (description[r.payment_type]))
            if float_compare(r.wallet_amount, r.amount, precision_rounding=currency.rounding) == 1:
                raise ValidationError(_("%s must not be greater than the payment amount which is %s") % (
                description[r.payment_type], r.amount))

    @api.depends('partner_id')
    def _compute_is_wallet(self):
        for r in self:
            r.is_wallet = False if r.partner_type != 'customer' or not r.partner_id else r.is_wallet

    @api.onchange('is_wallet', 'amount', 'currency_id')
    def _onchange_wallet_amount(self):
        self.wallet_amount = self.amount if self.is_wallet else 0

    def action_post(self):
        payments_todo = self.filtered('is_wallet')
        payments_todo._create_wallets_if_not_exist()
        for pay in payments_todo:
            wallet = pay.wallet_id
            wallet_amount = pay.wallet_amount
            if pay.payment_type == 'inbound':
                wallet.check_before_top_up_wallet(wallet_amount)
            else:
                if not wallet:
                    raise ValidationError(
                        _("The partner %s does not have any wallet to withdraw by the payment %s!") % (
                            pay.partner_id.display_name, pay.display_name
                        ))
                else:
                    wallet.check_before_withdraw_wallet(wallet_amount)

        # When a customer requests to to up/withdraw money from outside the portal page, a wallet top up/withdrawal transaction history
        # is created with the status 'pending'. So for this case we need to pass the transaction history creation process
        # handled in the `_post()` function of the `account.move` model and set to done with wallet transaction histories
        # have pending status.
        skip_creating_wallet_history = self.env.context.get('skip_creating_wallet_history', {})
        wallet_histories = payments_todo.move_id.line_ids.wallet_history_ids.filtered(
            lambda h: h.wallet_history_type in ['top-up', 'withdraw'] and h.state != 'cancel')
        for line in wallet_histories.account_move_line_ids:
            skip_creating_wallet_history[line.id] = line.wallet_history_ids.ids
        wallet_histories.filtered(lambda h: h.state == 'pending').with_context(
            skip_post_wallet_payment=True).action_done()
        self = self.with_context(skip_creating_wallet_history=skip_creating_wallet_history)

        return super(AccountPayment, self).action_post()

    def action_cancel(self):
        res = super(AccountPayment, self).action_cancel()
        payments_todo = self.filtered('is_wallet')
        wallet_histories = payments_todo.move_id.line_ids.wallet_history_ids.filtered(
            lambda h: h.wallet_history_type == 'withdraw')
        wallet_histories.filtered(lambda h: h.state == 'pending').action_cancel()
        return res

    def _create_wallets_if_not_exist(self):
        for r in self:
            if r.partner_id and r.is_wallet:
                r.wallet_id = r.partner_id._create_wallet_if_not_exist(r.wallet_type_id, r.currency_id)

    @api.model
    def _get_trigger_fields_to_synchronize(self):
        changed_fields = super(AccountPayment, self)._get_trigger_fields_to_synchronize()
        return changed_fields + ('wallet_amount', 'wallet_id')

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        """
        Override to add wallet fields into account move line if payment contain wallet
        """
        line_vals_list = super(AccountPayment, self)._prepare_move_line_default_vals(
            write_off_line_vals=write_off_line_vals, force_balance=force_balance
        )
        for line_vals in line_vals_list:
            if self.partner_type == 'customer' and line_vals.get('account_id', 0) == self.destination_account_id.id:
                line_vals.update({'wallet_id': self.wallet_id.id})
                if self.payment_type == 'inbound':
                    wallet_amount_currency = -1 * self.wallet_amount
                    line_vals.update({
                        'wallet_amount_currency': wallet_amount_currency,
                        'wallet_amount_residual_currency': wallet_amount_currency
                    })
        return line_vals_list
