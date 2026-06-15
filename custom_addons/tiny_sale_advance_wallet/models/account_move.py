# -*- coding: utf-8 -*-

from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        res = super().action_post()
        for move in self.filtered(lambda m: m.move_type in ('out_invoice', 'out_refund')):
            sale_order = move.mapped('line_ids.sale_line_ids.order_id')
            if not sale_order:
                continue
            wallet_advance_moves = sale_order.advance_line_ids.filtered(
                lambda l: l.advance_type == 'wallet'
                and l.state != 'cancel'
                and l.move_id
            ).mapped('move_id')
            if not wallet_advance_moves:
                continue
            widget = move.invoice_outstanding_credits_debits_widget
            if not widget:
                continue
            for data in widget.get('content', []):
                if data.get('move_id') in wallet_advance_moves.ids:
                    move.js_assign_outstanding_line(line_id=data.get('id'))
        return res
