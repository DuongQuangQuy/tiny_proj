from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    estimate_id = fields.Many2one(
        'sale.estimate', string='Phiếu dự toán', copy=False, readonly=True, index='btree_not_null')
