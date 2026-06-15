# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleAdvanceLine(models.Model):
    _name = 'sale.advance.line'
    _description = 'Sale Advance Line'
    _order = 'date desc, id desc'

    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    sale_id = fields.Many2one(
        comodel_name='sale.order',
        string='Sale Order',
        required=True,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
        related='sale_id.partner_invoice_id',
        store=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
    )
    advance_type = fields.Selection(
        selection=[
            ('cash', 'Cash'),
            ('bank', 'Bank'),
            ('wallet', 'Wallet'),
        ],
        string='Payment Method',
        required=True,
        default='bank',
    )
    transaction_type = fields.Selection(
        selection=[
            ('deposit', 'Deposit'),
            ('refund', 'Refund'),
        ],
        string='Transaction Type',
        required=True,
        default='deposit',
    )
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
    )
    state = fields.Selection(
        selection=[
            ('posted', 'Posted'),
            ('cancel', 'Cancelled'),
        ],
        string='State',
        compute='_compute_state',
        store=True,
    )
    payment_id = fields.Many2one(
        comodel_name='account.payment',
        string='Payment',
        ondelete='set null',
        copy=False,
    )
    wallet_history_id = fields.Many2one(
        comodel_name='wallet.history',
        string='Wallet History',
        ondelete='set null',
        copy=False,
    )
    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Journal Entry',
        ondelete='set null',
        copy=False,
    )

    @api.depends(
        'payment_id.state',
        'wallet_history_id.state',
        'move_id.state',
    )
    def _compute_state(self):
        for rec in self:
            if rec.advance_type == 'wallet':
                move = rec.move_id
                if move and move.state == 'cancel':
                    rec.state = 'cancel'
                else:
                    rec.state = 'posted'
            else:
                payment = rec.payment_id
                if payment and payment.state == 'cancel':
                    rec.state = 'cancel'
                else:
                    rec.state = 'posted'
