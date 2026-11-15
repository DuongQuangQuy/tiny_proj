# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    trial_id = fields.Many2one('sale.trial', string='Fitting', help='The work order at which the customer fitting takes place.')
