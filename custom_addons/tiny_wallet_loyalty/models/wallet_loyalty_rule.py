# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class WalletLoyaltyRule(models.Model):
    _name = 'wallet.loyalty.rule'
    _description = 'Wallet Loyalty Rule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'min_amount desc'

    name = fields.Char(string='Name', required=True, tracking=True)
    active = fields.Boolean(string='Active', default=True, tracking=True)
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company',
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id,
    )
    wallet_type_id = fields.Many2one(
        comodel_name='wallet.type', string='Apply To Wallet Type',
        help="Leave empty to apply to all wallet types.",
    )
    reward_wallet_type_id = fields.Many2one(
        comodel_name='wallet.type', string='Reward Wallet Type', required=True,
        help="The wallet type where the bonus will be credited (usually allow_top_up=False, allow_withdraw=False).",
    )
    min_amount = fields.Monetary(
        string='Minimum Top-Up Amount', currency_field='currency_id',
        required=True, tracking=True,
    )
    reward_type = fields.Selection(
        selection=[
            ('fixed', 'Fixed Amount'),
            ('percent', 'Percentage of Top-Up'),
        ],
        string='Reward Type', required=True, default='fixed', tracking=True,
    )
    reward_value = fields.Float(
        string='Reward Value', required=True, tracking=True, digits=(16, 2),
        help="Amount (if Fixed) or Percentage % (if Percentage). E.g. 10 means 10%.",
    )
    max_reward_amount = fields.Monetary(
        string='Max Reward Amount', currency_field='currency_id',
        help="Maximum bonus cap when Percentage type. Leave 0 for no cap.",
    )
    date_from = fields.Date(string='Valid From')
    date_to = fields.Date(string='Valid To')
    description = fields.Text(string='Description')

    @api.constrains('reward_value')
    def _check_reward_value(self):
        for r in self:
            if r.reward_value <= 0:
                raise ValidationError(_("Reward value must be greater than 0!"))
            if r.reward_type == 'percent' and r.reward_value > 100:
                raise ValidationError(_("Percentage reward cannot exceed 100%!"))

    @api.constrains('min_amount')
    def _check_min_amount(self):
        for r in self:
            if r.min_amount <= 0:
                raise ValidationError(_("Minimum top-up amount must be greater than 0!"))

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for r in self:
            if r.date_from and r.date_to and r.date_from > r.date_to:
                raise ValidationError(_("'Valid From' date must be before 'Valid To' date!"))

    def compute_reward(self, amount):
        self.ensure_one()
        if self.reward_type == 'fixed':
            return self.reward_value
        reward = amount * self.reward_value / 100.0
        if self.max_reward_amount and self.currency_id.compare_amounts(reward, self.max_reward_amount) > 0:
            reward = self.max_reward_amount
        return reward
