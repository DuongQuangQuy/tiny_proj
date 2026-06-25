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

        bonus_account = rule.reward_wallet_type_id.loyalty_bonus_account_id
        bonus_journal = rule.reward_wallet_type_id.loyalty_bonus_journal_id

        if not bonus_account or not bonus_journal:
            # Fallback khi chưa cấu hình kế toán: ghi history không có journal entry
            reward_wallet._create_wallet_history(
                amount=bonus,
                history_type='top-up',
                force_done=True,
                reference=_('Loyalty Bonus - %s') % rule.name,
            )
            return

        self._create_loyalty_bonus_move(rule, reward_wallet, bonus, bonus_account, bonus_journal)

    def _create_loyalty_bonus_move(self, rule, reward_wallet, bonus, bonus_account, bonus_journal):
        """
        Tạo journal entry cho bonus khuyến mãi:
          Nợ loyalty_bonus_account_id  (TK 641 / TK 3387 / TK 521)
          Có TK 131 (receivable)        gắn wallet_id → _post() tự tạo wallet.history
        """
        self.ensure_one()
        partner = self.partner_id.commercial_partner_id
        receivable_account = partner.property_account_receivable_id
        ref = _('Loyalty Bonus - %s') % rule.name
        company = self.env.company
        currency = self.currency_id

        # Quy đổi sang tiền công ty nếu khác currency
        bonus_company = currency._convert(
            bonus, company.currency_id, company, fields.Date.today()
        )

        debit_vals = {
            'account_id': bonus_account.id,
            'partner_id': partner.id,
            'name': ref,
            'debit': bonus_company,
            'credit': 0.0,
        }
        credit_vals = {
            'account_id': receivable_account.id,
            'partner_id': partner.id,
            'name': ref,
            'debit': 0.0,
            'credit': bonus_company,
            # wallet_amount_currency luôn theo currency của ví (= currency thanh toán)
            'wallet_id': reward_wallet.id,
            'wallet_amount_currency': -bonus,
        }

        # Thêm amount_currency khi dùng ngoại tệ
        if currency != company.currency_id:
            debit_vals.update({'currency_id': currency.id, 'amount_currency': bonus})
            credit_vals.update({'currency_id': currency.id, 'amount_currency': -bonus})

        move = self.env['account.move'].sudo().create({
            'journal_id': bonus_journal.id,
            'date': fields.Date.today(),
            'ref': ref,
            'line_ids': [(0, 0, debit_vals), (0, 0, credit_vals)],
        })
        # _post() → _add_wallet_balance() tự tạo wallet.history liên kết dòng 131
        move.action_post()
