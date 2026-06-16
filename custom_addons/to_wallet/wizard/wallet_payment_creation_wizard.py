from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError


class WalletPaymentCreationWizard(models.TransientModel):
    """This is a popup that supports quick creation of wallet top up/withdrawal payments"""
    _name = 'wallet.payment.creation.wizard'
    _description = 'Wallet Payment Creation Wizard'

    def _default_journal_id(self):
        journal_types = ['cash', 'bank']
        company = self.env['res.company'].browse(self._context.get('default_company_id', 0)) or self.env.company
        domain = [
            *self.env['account.journal']._check_company_domain(company),
            ('type', 'in', journal_types),
        ]

        journal = None
        currency_id = self._context.get('default_currency_id')
        if currency_id and currency_id != company.currency_id.id:
            currency_domain = domain + [('currency_id', '=', currency_id)]
            journal = self.env['account.journal'].search(currency_domain, limit=1)

        if not journal:
            journal = self.env['account.journal'].search(domain, limit=1)

        if not journal:
            error_msg = _(
                "No journal could be found in company %(company_name)s for any of those types: %(journal_types)s",
                company_name=company.display_name,
                journal_types=', '.join(journal_types),
            )
            raise UserError(error_msg)

        return journal

    wallet_type_id = fields.Many2one('wallet.type', string='Wallet Type', required=True, domain="[('company_id', 'in', [company_id, False])]")
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, domain="[('company_id', 'in', [company_id, False])]")
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    payment_date = fields.Date(string='Payment Date', default=fields.Date.today, required=True)
    confirm_payment = fields.Boolean(string='Confirm Payment', default=True)
    type = fields.Selection(selection=[('inbound', 'Top-Up'), ('outbound', 'Withdraw')], string='Payment Type', required=True, default='inbound')
    journal_id = fields.Many2one('account.journal', string='Journal', default=_default_journal_id,
        domain="[('company_id', 'in', [company_id, False]), ('type', 'in', ['cash', 'bank'])]")
    payment_ref = fields.Char(string='Reference')

    @api.onchange('payment_ref')
    def _onchange_payment_ref(self):
        if self.payment_ref:
            wallet_histories = self.env['wallet.history'].search([('reference', '=', self.payment_ref), ('state', '=', 'pending')])
            if not wallet_histories:
                raise ValidationError(_("There is no pending wallet transaction history has reference '%s'") % (self.payment_ref))

    def _prepare_payment_values(self):
        self.ensure_one()
        return {
            'partner_id': self.partner_id.id,
            'payment_type': self.type,
            'partner_type': 'customer',
            'is_wallet': True,
            'wallet_type_id': self.wallet_type_id.id,
            'company_id': self.company_id.id,
            'date': self.payment_date,
            'currency_id': self.currency_id.id,
            'journal_id': self.journal_id.id,
            'amount': self.amount,
            'wallet_amount': self.amount,
            'memo': self.payment_ref
        }

    def _create_payment(self):
        self.ensure_one()
        if self.currency_id.compare_amounts(self.amount, 0) <= 0:
            raise UserError(_("Amount must be greater than zero!"))
        payment = self.env['account.payment'].create(self._prepare_payment_values())
        wallet_histories = self.env['wallet.history'].search([('reference', '=', payment.memo), ('state', '=', 'pending')])
        skip_creating_wallet_history = self.env.context.get('skip_creating_wallet_history', {})
        move_line = payment.move_id.line_ids.filtered(lambda l: l.partner_id and l.account_id.account_type == 'asset_receivable')
        if wallet_histories:
            skip_creating_wallet_history[move_line.id] = wallet_histories.ids
            move_line.wallet_history_ids = [(4, h.id) for h in wallet_histories]
        if self.confirm_payment:
            payment.with_context(skip_creating_wallet_history=skip_creating_wallet_history).action_post()
        return payment

    def action_process(self):
        self.ensure_one()
        payment = self._create_payment()
        if payment.state == 'draft':
            action = self.env['ir.actions.act_window']._for_xml_id('account.action_account_payments')
            action['views'] = [(self.env.ref('account.view_account_payment_form').id, 'form')]
            action['res_id'] = payment.id
            return action
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("%s to wallet %s successful!") % (
                    _("Top-Up") if payment.payment_type == 'inbound' else _("Withdraw"),
                    payment.wallet_id.display_name
                ),
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
