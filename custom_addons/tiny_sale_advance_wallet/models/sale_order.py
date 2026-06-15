# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools import float_compare


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    advance_line_ids = fields.One2many(
        comodel_name='sale.advance.line',
        inverse_name='sale_id',
        string='Advance Lines',
    )

    @api.depends(
        'currency_id',
        'company_id',
        'amount_total',
        'account_payment_ids',
        'account_payment_ids.state',
        'account_payment_ids.move_id',
        'account_payment_ids.move_id.line_ids',
        'account_payment_ids.move_id.line_ids.date',
        'account_payment_ids.move_id.line_ids.debit',
        'account_payment_ids.move_id.line_ids.credit',
        'account_payment_ids.move_id.line_ids.currency_id',
        'account_payment_ids.move_id.line_ids.amount_currency',
        'invoice_ids',
        'invoice_ids.state',
        'invoice_ids.amount_residual',
        'advance_line_ids',
        'advance_line_ids.advance_type',
        'advance_line_ids.state',
        'advance_line_ids.move_id',
        'advance_line_ids.move_id.state',
        'advance_line_ids.move_id.line_ids.amount_residual',
        'advance_line_ids.move_id.line_ids.amount_residual_currency',
    )
    def _compute_advance_payment(self):
        super()._compute_advance_payment()
        for order in self:
            wallet_moves = order.advance_line_ids.filtered(
                lambda l: l.advance_type == 'wallet'
                and l.state != 'cancel'
                and l.move_id
            ).mapped('move_id')

            cr_lines = wallet_moves.mapped('line_ids').filtered(
                lambda l: l.account_id.account_type == 'asset_receivable'
                and not l.wallet_id
                and l.parent_state == 'posted'
            )

            wallet_amount = 0.0
            for line in cr_lines:
                line_currency = line.currency_id or line.company_id.currency_id
                line_amount = abs(
                    line.amount_residual_currency if line.currency_id
                    else line.amount_residual
                )
                if line_currency != order.currency_id:
                    line_amount = line_currency._convert(
                        line_amount, order.currency_id, order.company_id,
                        line.date or fields.Date.today(),
                    )
                wallet_amount += line_amount

            order.total_advance += wallet_amount
            order.amount_residual -= wallet_amount

            if wallet_amount > 0:
                has_due = float_compare(
                    order.amount_residual, 0.0,
                    precision_rounding=order.currency_id.rounding,
                )
                if has_due <= 0:
                    order.advance_payment_status = 'paid'
                else:
                    order.advance_payment_status = 'partial'
