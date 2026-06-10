# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountVoucherWizard(models.TransientModel):
    _inherit = 'account.voucher.wizard'

    is_wallet = fields.Boolean(string='Thanh toán qua Ví', default=False)
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Journal',
        required=False,
    )
    wallet_id = fields.Many2one(
        comodel_name='wallet',
        string='Wallet',
        domain="[('partner_id', '=', partner_id), ('company_id', '=', company_id)]",
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        compute='_compute_partner_id',
        store=False,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        compute='_compute_partner_id',
        store=False,
    )
    wallet_type_id = fields.Many2one(
        comodel_name='wallet.type',
        string='Wallet Type',
    )

    @api.depends('order_id')
    def _compute_partner_id(self):
        for wzd in self:
            wzd.partner_id = wzd.order_id.partner_invoice_id.commercial_partner_id
            wzd.company_id = wzd.order_id.company_id

    @api.onchange('is_wallet')
    def _onchange_is_wallet(self):
        if not self.is_wallet:
            self.wallet_id = False
            self.wallet_type_id = False

    @api.onchange('wallet_type_id', 'order_id')
    def _onchange_wallet_type_id(self):
        if self.is_wallet and self.wallet_type_id and self.order_id:
            partner = self.order_id.partner_invoice_id.commercial_partner_id
            wallet = partner._create_wallet_if_not_exist(
                self.wallet_type_id,
                self.order_id.currency_id
            )
            self.wallet_id = wallet

    def _get_advance_type_from_journal(self, journal):
        if journal.type == 'cash':
            return 'cash'
        return 'bank'

    def _check_wallet_balance(self, wallet, amount):
        if not wallet:
            raise UserError(self.env._("Vui lòng chọn ví để đặt cọc!"))
        if wallet.currency_id.compare_amounts(wallet.amount, amount) < 0:
            raise UserError(
                self.env._(
                    "Số dư ví không đủ! (Số dư hiện tại: %s %s)"
                ) % (wallet.amount, wallet.currency_id.name)
            )

    def _prepare_wallet_advance_vals(self, sale, wallet, amount):
        return {
            'date': self.date,
            'sale_id': sale.id,
            'company_id': sale.company_id.id,
            'currency_id': sale.currency_id.id,
            'advance_type': 'wallet',
            'transaction_type': 'deposit',
            'amount': amount,
        }

    def _create_wallet_advance(self, sale):
        self.ensure_one()
        wallet = self.wallet_id
        amount = self.currency_amount
        self._check_wallet_balance(wallet, amount)

        wallet_history = wallet._create_wallet_history(
            amount=-1 * amount,
            history_type='payment',
            force_done=True,
        )

        advance_vals = self._prepare_wallet_advance_vals(sale, wallet, amount)
        advance_vals['wallet_history_id'] = wallet_history.id
        self.env['sale.advance.line'].create(advance_vals)

    def _create_cash_bank_advance(self, sale):
        self.ensure_one()
        payment_obj = self.env['account.payment']
        payment_vals = self._prepare_payment_vals(sale)
        payment = payment_obj.create(payment_vals)
        sale.account_payment_ids |= payment
        payment.action_post()

        advance_type = self._get_advance_type_from_journal(self.journal_id)
        transaction_type = 'refund' if self.payment_type == 'outbound' else 'deposit'
        self.env['sale.advance.line'].create({
            'date': self.date,
            'sale_id': sale.id,
            'company_id': sale.company_id.id,
            'currency_id': self.journal_currency_id.id,
            'advance_type': advance_type,
            'transaction_type': transaction_type,
            'amount': self.currency_amount,
            'payment_id': payment.id,
        })

    def _check_refund_wallet(self, sale, amount):
        advance_lines = sale.advance_line_ids.filtered(lambda l: l.state != 'cancel')
        total_deposit = sum(advance_lines.filtered(lambda l: l.transaction_type == 'deposit').mapped('amount'))
        total_refund = sum(advance_lines.filtered(lambda l: l.transaction_type == 'refund').mapped('amount'))
        remaining = total_deposit - total_refund
        if self.env.company.currency_id.compare_amounts(remaining, 0) <= 0:
            raise UserError(self.env._("Không có khoản đặt cọc nào còn lại để hoàn trả!"))
        return remaining

    def _create_wallet_refund(self, sale):
        self.ensure_one()
        wallet = self.wallet_id
        if not wallet:
            raise UserError(self.env._("Vui lòng chọn ví để hoàn cọc!"))
        amount = self.currency_amount
        remaining_wallet = self._check_refund_wallet(sale, amount)

        wallet_advance_lines = sale.advance_line_ids.filtered(
            lambda l: l.advance_type == 'wallet' and l.state != 'cancel'
        )
        wallet_deposited = sum(wallet_advance_lines.filtered(lambda l: l.transaction_type == 'deposit').mapped('amount'))
        wallet_refunded = sum(wallet_advance_lines.filtered(lambda l: l.transaction_type == 'refund').mapped('amount'))
        remaining_wallet_advance = wallet_deposited - wallet_refunded

        currency = sale.currency_id

        advance_line_obj = self.env['sale.advance.line']
        base_vals = {
            'date': self.date,
            'sale_id': sale.id,
            'company_id': sale.company_id.id,
            'currency_id': currency.id,
            'advance_type': 'wallet',
            'transaction_type': 'refund',
        }

        if currency.compare_amounts(remaining_wallet_advance, 0) > 0:
            refund_amount = min(amount, remaining_wallet_advance)
            refund_history = wallet._create_wallet_history(
                amount=refund_amount,
                history_type='refund',
                force_done=True,
            )
            advance_line_obj.create({
                **base_vals,
                'amount': refund_amount,
                'wallet_history_id': refund_history.id,
            })

            topup_amount = amount - refund_amount
            if currency.compare_amounts(topup_amount, 0) > 0:
                topup_history = wallet._create_wallet_history(
                    amount=topup_amount,
                    history_type='top-up',
                    force_done=True,
                )
                advance_line_obj.create({
                    **base_vals,
                    'amount': topup_amount,
                    'wallet_history_id': topup_history.id,
                })
        else:
            topup_history = wallet._create_wallet_history(
                amount=amount,
                history_type='top-up',
                force_done=True,
            )
            advance_line_obj.create({
                **base_vals,
                'amount': amount,
                'wallet_history_id': topup_history.id,
            })

    def make_advance_payment(self):
        self.ensure_one()
        sale_ids = self.env.context.get('active_ids', [])
        if not sale_ids:
            return {'type': 'ir.actions.act_window_close'}
        sale = self.env['sale.order'].browse(sale_ids[0])

        if self.is_wallet:
            if self.payment_type == 'inbound':
                self._create_wallet_advance(sale)
            else:
                self._create_wallet_refund(sale)
        else:
            if not self.journal_id:
                raise UserError(self.env._("Vui lòng chọn phương thức thanh toán (Journal)!"))
            if self.payment_type == 'outbound':
                advance_lines = sale.advance_line_ids.filtered(lambda l: l.state != 'cancel')
                total_deposit = sum(advance_lines.filtered(lambda l: l.transaction_type == 'deposit').mapped('amount'))
                total_refund = sum(advance_lines.filtered(lambda l: l.transaction_type == 'refund').mapped('amount'))
                if sale.currency_id.compare_amounts(total_deposit - total_refund, 0) <= 0:
                    raise UserError(self.env._("Không có khoản đặt cọc nào còn lại để hoàn trả!"))
            self._create_cash_bank_advance(sale)

        return {'type': 'ir.actions.act_window_close'}
