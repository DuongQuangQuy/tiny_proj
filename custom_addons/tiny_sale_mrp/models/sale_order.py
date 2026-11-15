from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    estimate_id = fields.Many2one(
        'sale.estimate', string='Estimate', copy=False, readonly=True, index='btree_not_null')
