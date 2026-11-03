from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    # Dấu tích dòng NVL vải lót: tự tích theo danh mục sản phẩm (NVL vải lót), cho phép sửa tay
    is_lining = fields.Boolean(string='Vải lót', compute='_compute_is_lining', store=True, readonly=False)

    @api.depends('product_id')
    def _compute_is_lining(self):
        for move in self:
            move.is_lining = move.product_id.categ_id.is_lining
