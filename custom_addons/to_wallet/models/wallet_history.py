from odoo import fields, models, api, _
from odoo.exceptions import AccessError
from odoo.addons.payment import utils as payment_utils


class WalletHistory(models.Model):
    _name = 'wallet.history'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Wallet History'
    _mail_post_access = 'read'
    _order = 'create_date desc'

    name = fields.Char(string='Transaction Code', required=True, readonly=True)
    wallet_id = fields.Many2one(comodel_name='wallet', string='Wallet', required=True, ondelete='restrict', readonly=True)
    partner_id = fields.Many2one(related='wallet_id.partner_id', store=True, index='btree_not_null', precompute=True, readonly=True)
    wallet_type_id = fields.Many2one(related='wallet_id.wallet_type_id', store=True, precompute=True, readonly=True)
    company_id = fields.Many2one(related='wallet_id.company_id', store=True, precompute=True, readonly=True)
    currency_id = fields.Many2one(related='wallet_id.currency_id', store=True, precompute=True, readonly=True)
    amount = fields.Monetary(string='Amount', currency_field='currency_id', readonly=True)
    state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('done', 'Successful'),
            ('cancel', 'Cancelled')
        ], tracking=True,
        string='State', required=True, default='pending', readonly=True
    )
    reference = fields.Char(string='Reference', readonly=True)
    date = fields.Datetime(string='Success Date', readonly=True, tracking=True)
    # Cases where a wallet transaction history is associated with multiple journal items:
    # - Top up your wallet from many NCC bills
    # - Collect payments on behalf of the Marketplace
    # - Pay multiple customer invoices in one go
    # - ...
    account_move_line_ids = fields.Many2many(
        comodel_name='account.move.line', string='Journal Item', readonly=True,
    )
    account_move_line_count = fields.Integer(
        string='Journal Items Count',
        compute='_compute_account_move_line_count', compute_sudo=True,
    )
    payment_ids = fields.Many2many(comodel_name='account.payment', string='Payment', compute='_compute_payment_ids')
    payment_transaction_id = fields.Many2one('payment.transaction', string='Payment Transaction')
    wallet_history_type = fields.Selection(
        selection=[
            ('top-up', 'Top-Up'),
            ('withdraw', 'Withdrawal'),
            ('payment', 'Payment'),
            ('refund', 'Refund')
        ],
        string='Wallet Transaction History Type', required=True, default='top-up'
    )

    @api.depends('account_move_line_ids')
    def _compute_account_move_line_count(self):
        for r in self:
            r.account_move_line_count = len(r.account_move_line_ids)

    @api.depends('account_move_line_ids.move_id.payment_ids')
    def _compute_payment_ids(self):
        for r in self:
            r.payment_ids = r.account_move_line_ids.move_id.payment_ids

    def action_done(self):
        if not self.env.su and not self.env.is_superuser() and not self.env.user.has_group('account.group_account_invoice'):
            raise AccessError(
                _("You are not allowed to done this wallet transaction history! Contact your administrator to request access if necessary.")
            )
        for history in self:
            # In some cases, transaction history is created in the 'pending' state but is not associated with any journal
            # items. When done such transaction history, the system will open a pop-up to create a corresponding payment
            # (For example, this case may occur when the user tops up the wallet from the portal using the payment method Wire Transfer).
            wallet_history_type = history.wallet_history_type
            if wallet_history_type in ['top-up', 'withdraw'] and history.payment_transaction_id and not history.payment_id:
                ctx = {
                    'default_type': 'inbound' if wallet_history_type == 'top-up' else 'outbound',
                    'default_amount': history.amount,
                    'default_payment_ref': history.reference
                }
                action = history.with_context(**ctx).wallet_id.action_create_payment()
                action['context'].update(ctx)
                return action
        self.sudo()._set_done()

    def _set_done(self):
        histories_to_done = self.filtered(lambda h: h.state == 'pending')
        if not self.env.context.get('skip_post_wallet_payment', False):
            histories_to_done.account_move_line_ids.move_id.filtered(lambda m: m.state == 'draft').action_post()
        histories_to_done.write({'state': 'done', 'date': fields.Datetime.now()})
        for r in histories_to_done:
            r.wallet_id._send_mail_notice_wallet_fluctuation(wallet_history=r)

    def action_cancel(self):
        if not self.env.su and not self.env.is_superuser() and not self.env.user.has_group('account.group_account_invoice'):
            raise AccessError(
                _("You are not allowed to cancel this wallet transaction history! Contact your administrator to request access if necessary.")
            )
        self.sudo()._set_cancel()

    def _set_cancel(self):
        histories_to_cancel = self.filtered(lambda h: h.state != 'cancel')
        histories_to_cancel.write({'state': 'cancel'})

    def action_view_account_move_lines(self):
        move_lines = self.account_move_line_ids
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_account_moves_all')
        action['context'] = {'search_default_posted': 1, 'search_default_receivable': 1}
        action['domain'] = [('id', 'in', move_lines.ids)]
        return action

    @api.model_create_multi
    def create(self, vals_list):
        """
        1. Generate name (code) for wallet histories
        2. Update Reference for wallet histories by payments or default
        3. Update Memo (ref) for the related payment
        4. Add Activity if wallet history state is pending
        """
        # 1. Generate name (code) for wallet histories
        for vals in vals_list:
            vals['name'] = payment_utils.singularize_reference_prefix(prefix='', separator='')

        wallet_histories = super(WalletHistory, self).create(vals_list)

        activity_type = self.env.ref('mail.mail_activity_data_todo')
        context = self.env.context
        description_selection = {k: v for k, v in self._fields['wallet_history_type']._description_selection(self.env)}

        for history in wallet_histories:
            history_type = history.wallet_history_type

            # 2. Update Reference for wallet histories by payments or default
            # Lấy ref từ tất cả payments (bỏ qua ref rỗng), join bằng ", "
            payment_refs = ', '.join(filter(None, history.payment_ids.mapped('memo')))
            history.reference = payment_refs or f'WALLET/{history_type.upper()}/{history.name}'

            # 3. Update Memo (ref) for the related payments
            for payment in history.payment_ids:
                payment.memo = payment.memo or history.reference

            # 4. Add Activity and assign the user if wallet history state is pending.
            if not context.get('force_done', False):
                date_deadline = history.create_date.date()
                for notice_recipient in history.wallet_type_id.notice_recipient_ids:
                    history.sudo().activity_schedule(
                        date_deadline=date_deadline,
                        activity_type_id=activity_type.id,
                        summary=_("Verify wallet %s history.") % (description_selection[history_type].lower()),
                        user_id=notice_recipient.id
                    )

        return wallet_histories
