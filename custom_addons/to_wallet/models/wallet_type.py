from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class WalletType(models.Model):
    _name = 'wallet.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Wallet Type'
    _mail_post_access = 'read'

    name = fields.Char(string='Name', required=True, translate=True, tracking=True)
    allow_top_up = fields.Boolean(string='Allow Top Up', default=True, tracking=True)
    allow_withdraw = fields.Boolean(string='Allow Withdraw', default=True, tracking=True)
    allow_pay_online = fields.Boolean(string='Allow Use To Pay Online', default=True, tracking=True)
    description = fields.Text(string='Description')
    company_id = fields.Many2one(comodel_name='res.company', string='Company', default=lambda self: self.env.company)
    wallet_ids = fields.One2many(comodel_name='wallet', inverse_name='wallet_type_id', string='Wallets')
    wallets_count = fields.Integer(string='Wallets Count', compute='_compute_wallets_count')
    wallet_history_ids = fields.One2many(
        comodel_name='wallet.history', inverse_name='wallet_type_id',
        string='Transaction Histories'
    )
    wallet_histories_count = fields.Integer(string='Transaction Histories Count', compute='_compute_wallet_histories_count')
    notice_recipient_ids = fields.Many2many(
        comodel_name='res.users', string='Notification Recipient',
        help="When there is a request to withdraw or top up money from a customer, the user set up here will receive a notification."
    )

    @api.depends('wallet_ids')
    def _compute_wallets_count(self):
        grouped_data = self.env['wallet']._read_group([('wallet_type_id', 'in', self.ids)], ['wallet_type_id'], ['__count'])
        mapped_data = {record.id: count for record, count in grouped_data}
        for r in self:
            r.wallets_count = mapped_data.get(r.id, 0)

    @api.depends('wallet_history_ids')
    def _compute_wallet_histories_count(self):
        grouped_data = self.env['wallet.history']._read_group([('wallet_type_id', 'in', self.ids)], ['wallet_type_id'], ['__count'])
        mapped_data = {record.id: count for record, count in grouped_data}
        for r in self:
            r.wallet_histories_count = mapped_data.get(r.id, 0)

    def action_view_wallet(self):
        wallets = self.wallet_ids
        action = self.env['ir.actions.act_window']._for_xml_id('to_wallet.action_view_wallets')
        if len(wallets) != 1:
            action['domain'] = [('id', 'in', wallets.ids)]
        else:
            res = self.env.ref('to_wallet.wallet_form', False)
            action['views'] = [(res and res.id or False, 'form')]
            action['res_id'] = wallets.id
        return action

    def action_view_wallet_history(self):
        histories = self.wallet_history_ids
        action = self.env['ir.actions.act_window']._for_xml_id('to_wallet.action_view_wallet_histories')
        if len(histories) != 1:
            action['domain'] = [('id', 'in', histories.ids)]
        else:
            res = self.env.ref('to_wallet.wallet_history_form', False)
            action['views'] = [(res and res.id or False, 'form')]
            action['res_id'] = histories.id
        return action

    @api.model
    def _check_wallet_history_type(self, wallet_history_type):
        wallet_history_types = self.env['wallet.history']._fields['wallet_history_type'].get_values(self.env)
        if wallet_history_type not in wallet_history_types:
            raise ValidationError(
                _("Operation \'%s\' is not supported. Supported operations: %s") % (wallet_history_type, ', '.join(wallet_history_types))
            )

    def show_button_top_up_wallet_on_portal(self):
        self.ensure_one()
        return self.allow_top_up

    def show_button_withdraw_wallet_on_portal(self):
        self.ensure_one()
        return self.allow_withdraw
