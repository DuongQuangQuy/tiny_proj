import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    product_size = fields.Char(string='Số đo')
    note = fields.Text(string='Ghi chú')
    default_code = fields.Char(string='Mã tham chiếu')
    product_pattern_id = fields.Many2one('product.product', string='Mã họa tiết')
    product_pattern_image = fields.Binary(string='Ảnh họa tiết')
    note_pattern = fields.Text(string='Ghi chú họa tiết')
    code_fabric = fields.Char(
        string='Mã vải', compute='_compute_code_fabric', store=True, readonly=False, precompute=True)

    @api.onchange('product_pattern_id')
    def onchange_sale_product_pattern_image(self):
        for line in self:
            if line.product_pattern_id.image_128:
                line.product_pattern_image = line.product_pattern_id.image_128
            else:
                line.product_pattern_image = False

    @api.depends('product_id')
    def _compute_code_fabric(self):
        # code_fabric khai báo riêng trên cả product.product và product.template:
        # ưu tiên biến thể, nếu trống thì lấy từ template (nơi người dùng nhập trên form sản phẩm)
        for rec in self:
            product = rec.product_id
            rec.code_fabric = (product.code_fabric or product.product_tmpl_id.code_fabric) if product else False

