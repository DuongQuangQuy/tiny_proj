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
        'advance_line_ids.state',
        'advance_line_ids.amount',
        'advance_line_ids.transaction_type',
        'advance_line_ids.advance_type',
    )
    def _compute_advance_payment(self):
        super()._compute_advance_payment()
        for order in self:
            wallet_lines = order.advance_line_ids.filtered(
                lambda l: l.advance_type == 'wallet' and l.state != 'cancel'
            )
            wallet_deposit = sum(
                wallet_lines.filtered(lambda l: l.transaction_type == 'deposit').mapped('amount')
            )
            wallet_refund = sum(
                wallet_lines.filtered(lambda l: l.transaction_type == 'refund').mapped('amount')
            )
            wallet_net = wallet_deposit - wallet_refund

            order.total_advance += wallet_net
            order.amount_residual -= wallet_net

            if wallet_net > 0:
                has_due = float_compare(
                    order.amount_residual, 0.0,
                    precision_rounding=order.currency_id.rounding
                )
                if has_due <= 0:
                    order.advance_payment_status = 'paid'
                else:
                    order.advance_payment_status = 'partial'
