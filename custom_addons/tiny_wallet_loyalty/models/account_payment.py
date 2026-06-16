# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    loyalty_rule_id = fields.Many2one(
        comodel_name='wallet.loyalty.rule',
        string='Loyalty Promotion',
        copy=False,
        tracking=True,
    )
    loyalty_bonus_amount = fields.Monetary(
        string='Estimated Bonus',
        currency_field='currency_id',
        compute='_compute_loyalty_bonus_amount',
    )

    @api.depends('loyalty_rule_id', 'wallet_amount')
    def _compute_loyalty_bonus_amount(self):
        for r in self:
            if r.loyalty_rule_id and r.wallet_amount:
                r.loyalty_bonus_amount = r.loyalty_rule_id.compute_reward(r.wallet_amount)
            else:
                r.loyalty_bonus_amount = 0.0

    def action_post(self):
        res = super().action_post()
        if self.env.context.get('loyalty_handled_externally'):
            return res
        for payment in self.filtered(
            lambda p: p.is_wallet
            and p.payment_type == 'inbound'
            and p.state == 'paid'
            and p.wallet_type_id
            and p.loyalty_rule_id
        ):
            payment._apply_loyalty_reward(payment.loyalty_rule_id)
        return res

    def _apply_loyalty_reward(self, rule):
        self.ensure_one()
        bonus = rule.compute_reward(self.wallet_amount)
        if self.currency_id.compare_amounts(bonus, 0) <= 0:
            return
        reward_wallet = self.partner_id._create_wallet_if_not_exist(
            rule.reward_wallet_type_id, self.currency_id
        )
        reward_wallet._create_wallet_history(
            amount=bonus,
            history_type='top-up',
            force_done=True,
            reference=_("Loyalty Bonus - %s") % rule.name,
        )
