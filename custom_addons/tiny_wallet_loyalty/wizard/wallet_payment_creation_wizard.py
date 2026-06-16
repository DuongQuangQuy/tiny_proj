# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class WalletPaymentCreationWizard(models.TransientModel):
    _inherit = 'wallet.payment.creation.wizard'

    loyalty_rule_id = fields.Many2one(
        comodel_name='wallet.loyalty.rule',
        string='Loyalty Promotion',
    )
    loyalty_bonus_amount = fields.Monetary(
        string='Estimated Bonus',
        currency_field='currency_id',
        compute='_compute_loyalty_bonus_amount',
    )

    @api.depends('loyalty_rule_id', 'amount')
    def _compute_loyalty_bonus_amount(self):
        for r in self:
            if r.loyalty_rule_id and r.amount:
                r.loyalty_bonus_amount = r.loyalty_rule_id.compute_reward(r.amount)
            else:
                r.loyalty_bonus_amount = 0.0

    @api.onchange('amount', 'wallet_type_id', 'currency_id', 'type')
    def _onchange_loyalty_auto_select(self):
        if self.type != 'inbound' or not self.amount or self.amount <= 0:
            self.loyalty_rule_id = False
            return
        today = fields.Date.today()
        domain = [
            ('active', '=', True),
            ('currency_id', '=', self.currency_id.id),
            ('min_amount', '<=', self.amount),
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id),
            '|', ('wallet_type_id', '=', False), ('wallet_type_id', '=', self.wallet_type_id.id),
            '|', ('date_from', '=', False), ('date_from', '<=', today),
            '|', ('date_to', '=', False), ('date_to', '>=', today),
        ]
        rules = self.env['wallet.loyalty.rule'].search(domain)
        if not rules:
            self.loyalty_rule_id = False
        elif len(rules) == 1:
            self.loyalty_rule_id = rules
        elif self.loyalty_rule_id not in rules:
            self.loyalty_rule_id = False

    def _create_payment(self):
        return super(WalletPaymentCreationWizard, self.with_context(loyalty_handled_externally=True))._create_payment()

    def action_process(self):
        self.ensure_one()
        payment = self._create_payment()
        if payment.state == 'draft':
            action = self.env['ir.actions.act_window']._for_xml_id('account.action_account_payments')
            action['views'] = [(self.env.ref('account.view_account_payment_form').id, 'form')]
            action['res_id'] = payment.id
            return action
        if (
            payment.is_wallet
            and payment.payment_type == 'inbound'
            and payment.wallet_id
            and self.loyalty_rule_id
        ):
            payment._apply_loyalty_reward(self.loyalty_rule_id)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("%s to wallet %s successful!") % (
                    _("Top-Up") if payment.payment_type == 'inbound' else _("Withdraw"),
                    payment.wallet_id.display_name,
                ),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
