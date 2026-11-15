# -*- coding: utf-8 -*-
from odoo import fields, models


class WalletType(models.Model):
    _inherit = 'wallet.type'

    loyalty_bonus_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Loyalty Bonus Account',
        domain="[('company_ids', 'in', [company_id, False])]",
        help='Debit account when a promotion bonus is credited to this wallet. Main wallet (withdrawable): use account 641 or 521. Promotion wallet (not withdrawable): use account 3387.',
    )
    loyalty_bonus_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Loyalty Bonus Journal',
        domain="[('type', '=', 'general'), ('company_id', 'in', [company_id, False])]",
        help='Miscellaneous journal (type=general) used to create the journal entry when the promotion bonus is credited.',
    )
