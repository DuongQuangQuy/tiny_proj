from odoo import models, fields, api, _
from odoo.tools import format_datetime
from odoo.exceptions import ValidationError


class Wallet(models.Model):
    _name = 'wallet'
    _description = 'Wallet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _mail_post_access = 'read'

    name = fields.Char(compute='_compute_name', compute_sudo=True)
    currency_id = fields.Many2one('res.currency', required=True, readonly=True)
    partner_id = fields.Many2one('res.partner', required=True, readonly=True, index=True)
    amount = fields.Monetary(
        string='Available Balance', currency_field='currency_id',
        compute=lambda r: r._compute_amount('amount', 'done'),
        depends=['wallet_history_ids.state', 'wallet_history_ids.amount'],
        store=True, tracking=True,
    )
    amount_pending = fields.Monetary(
        string='Pending Balance', currency_field='currency_id',
        compute=lambda r: r._compute_amount('amount_pending', 'pending'),
        depends=['wallet_history_ids.state', 'wallet_history_ids.amount'],
        store=True, tracking=True,
    )
    payment_ids = fields.One2many('account.payment', 'wallet_id', groups="account.group_account_invoice")
    payments_count = fields.Integer(compute='_compute_payments_count', groups="account.group_account_invoice")
    wallet_type_id = fields.Many2one(comodel_name='wallet.type', string='Wallet Type', tracking=True, ondelete='restrict')
    allow_top_up = fields.Boolean(related='wallet_type_id.allow_top_up')
    allow_withdraw = fields.Boolean(related='wallet_type_id.allow_withdraw')
    wallet_history_ids = fields.One2many(comodel_name='wallet.history', inverse_name='wallet_id', string='Transaction Histories')
    wallet_histories_count = fields.Integer(string='Transaction Histories Count', compute='_compute_wallet_histories_count')
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company',
        required=True, default=lambda self: self.env.company
    )
    move_line_ids = fields.Many2many(
        'account.move.line', string='Journal Items', readonly=True,
        compute='_compute_move_line_ids', groups="account.group_account_invoice"
    )
    move_lines_count = fields.Integer(
        string='Journal Items Count',
        compute='_compute_move_lines_count', compute_sudo=True
        )

    _sql_constraints = [
        (
            'currency_per_partner_uniq',
            'unique(company_id, partner_id, wallet_type_id, currency_id)',
            'Wallet error. Currency must be unique for per wallet type.'
        )
    ]

    @api.depends('wallet_type_id', 'currency_id')
    def _compute_name(self):
        for r in self:
            r.name = f'{r.wallet_type_id.name} ({r.currency_id.name})'

    @api.depends('wallet_history_ids')
    def _compute_wallet_histories_count(self):
        grouped_data = self.env['wallet.history']._read_group([('wallet_id', 'in', self.ids)], ['wallet_id'], ['__count'])
        mapped_data = {record.id: count for record, count in grouped_data}
        for r in self:
            r.wallet_histories_count = mapped_data.get(r.id, 0)

    def _compute_amount(self, field_name, default_value=False):
        domain = [
            ('wallet_id', 'in', self.ids),
            ('state', '=', default_value),
        ]
        grouped_data = self.env['wallet.history']._read_group(domain, ['wallet_id'], ['amount:sum'])
        mapped_data = {record.id: value for record, value in grouped_data}
        for r in self:
            r[field_name] = mapped_data.get(r.id, 0)

    @api.depends('wallet_history_ids')
    def _compute_move_line_ids(self):
        for r in self:
            r.move_line_ids = r.wallet_history_ids.account_move_line_ids

    @api.depends('move_line_ids')
    def _compute_move_lines_count(self):
        for r in self:
            r.move_lines_count = len(r.move_line_ids)

    @api.depends('payment_ids')
    def _compute_payments_count(self):
        for r in self:
            r.payments_count = len(r.payment_ids)

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

    def action_view_account_move_lines(self):
        move_lines = self.move_line_ids
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_account_moves_all')
        action['context'] = {'search_default_posted': 1, 'search_default_receivable': 1}
        action['domain'] = [('id', 'in', move_lines.ids)]
        return action

    def action_create_payment(self):
        self.ensure_one()
        payment_type = self._context.get('default_type', False)
        result = {
            'type': 'ir.actions.act_window',
            'name': _("Top Up Wallet") if payment_type and payment_type == 'inbound' else _("Withdraw Wallet"),
            'view_mode': 'form',
            'res_model': 'wallet.payment.creation.wizard',
            'target': 'new',
            'views': [[self.env.ref('to_wallet.wallet_payment_creation_wizard_form_views').id, 'form']],
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_currency_id': self.currency_id.id,
                'default_company_id': self.company_id.id,
                'default_wallet_type_id': self.wallet_type_id.id
            }
        }
        return result

    @api.depends('partner_id.name', 'name')
    def _compute_display_name(self):
        super(Wallet, self)._compute_display_name()
        for r in self:
            r.display_name = f'[{r.partner_id.display_name}] {r.name}'

    def check_before_top_up_wallet(self, amount):
        self.ensure_one()
        if not self.wallet_type_id.allow_top_up:
            raise ValidationError(_("Invalid operation. The selected wallet type does not support top up!"))

    def check_before_withdraw_wallet(self, amount):
        self.ensure_one()
        if not self.wallet_type_id.allow_withdraw:
            raise ValidationError(_("Invalid operation. The selected wallet type does not support withdraw!"))
        # To avoid partners sending too many withdrawal requests, we compare the total number of previous withdrawal
        # requests through the pending wallet transaction history with the available balance.
        pending_withdraw_histories = self.wallet_history_ids.filtered(
            lambda h: h.state == 'pending' and h.wallet_history_type == 'withdraw'
        )
        if pending_withdraw_histories:
            total_pending_withdrawals = sum(pending_withdraw_histories.mapped('amount'))
            if self.env.context.get('portal_check_before_top_up_or_withdraw_wallet', False) \
                and self.currency_id.compare_amounts(self.amount, amount + abs(total_pending_withdrawals)) < 0:
                raise ValidationError(
                    _("The amount to withdraw exceeds the available balance! (Pending: %s, Demand: %s, Availability: %s)") % (
                        self.currency_id.format(abs(total_pending_withdrawals)),
                        self.currency_id.format(amount),
                        self.currency_id.format(self.amount)
                    )
                )
        if self.currency_id.compare_amounts(amount, self.amount) > 0:
            raise ValidationError(_(
                "Wallet balance is unavailable! (Remaining balance: %d %s)") % (self.amount, self.currency_id.name)
            )

    def _prepare_wallet_history_vals(self, amount, history_type, **extra_vals):
        self.ensure_one()
        return {
            'wallet_id': self.id,
            'amount': amount,
            'wallet_history_type': history_type,
            **extra_vals
        }

    def _create_wallet_history(self, amount, history_type, force_done=False, **extra_vals):
        self.ensure_one()
        self.wallet_type_id._check_wallet_history_type(history_type)
        vals = self._prepare_wallet_history_vals(amount, history_type, **extra_vals)
        history = self.env['wallet.history'].sudo().with_context(force_done=force_done).create(vals)
        if force_done:
            history.action_done()
        return history

    def _reconcile_wallet(self, debit_amls):
        self.ensure_one()
        context = self.env.context
        credit_amls = self.move_line_ids.filtered(
            lambda aml: aml.credit > 0 and aml.move_id.state == 'posted' and not aml.reconciled
            and not aml.currency_id.is_zero(aml.wallet_amount_residual_currency)
        )
        (debit_amls | credit_amls).with_context(**context).reconcile()

    def _send_mail_notice_wallet_fluctuation(self, wallet_history, **kwargs):
        """
        :param kwargs: optional values to create mail.compose.message
        """
        self.ensure_one()
        template = self.env.ref('to_wallet.mail_template_wallet_fluctuation_notification')
        email_from = self.company_id.email_formatted or self.env.user.email_formatted
        if not template or not email_from:
            return
        add_context = {'format_datetime': format_datetime, 'wallet_history': wallet_history}

        def _render_field(field, wallet, template, **kw):
            return template.sudo()._render_field(field=field, res_ids=wallet.ids, compute_lang=True, **kw)[wallet.id]

        self.message_post(
            subject=_render_field(field='subject', wallet=self, template=template),
            body=_render_field(field='body_html', wallet=self, template=template, add_context=add_context),
            message_type='comment',
            email_layout_xmlid='mail.mail_notification_light',
            email_from=email_from,
            partner_ids=self.partner_id.ids,
            **kwargs
        )
