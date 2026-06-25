# -*- coding: utf-8 -*-
from odoo import fields, models


class WalletType(models.Model):
    _inherit = 'wallet.type'

    loyalty_bonus_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Loyalty Bonus Account',
        domain="[('company_ids', 'in', [company_id, False])]",
        help="Tài khoản Nợ khi ghi nhận bonus khuyến mãi vào ví này. "
             "Ví chính (rút được): dùng TK 641 hoặc TK 521. "
             "Ví KM (không rút): dùng TK 3387.",
    )
    loyalty_bonus_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Loyalty Bonus Journal',
        domain="[('type', '=', 'general'), ('company_id', 'in', [company_id, False])]",
        help="Nhật ký hỗn hợp (type=general) dùng để tạo bút toán khi cộng bonus khuyến mãi.",
    )
