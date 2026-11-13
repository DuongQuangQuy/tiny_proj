# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    trial_id = fields.Many2one('sale.trial', string='Thử hàng', help='Thử hàng ở công đoạn nào')
