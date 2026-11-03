import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    code_fabric = fields.Char(string='Mã vải')
    note = fields.Text(string='Ghi chú')
    # Khai báo trên template: product.product kế thừa qua _inherits (product_tmpl_id)
    # nên đọc/ghi ở variant sẽ đồng bộ với template và ngược lại.
    fabric_name_standard = fields.Char(string='Tên vải theo chuẩn kho')
    fabric_name_vendor = fields.Char(string='Tên vải theo cách gọi của NCC')
    is_zipper = fields.Boolean(string='Là NVL dây kéo', default=False)
    # Matching Zipper Color: nhiều mã vải có thể dùng chung một mã dây kéo
    matching_zipper_tmpl_id = fields.Many2one('product.template', string='Dây kéo cùng màu')
    # Vải lót: chỉ chọn sản phẩm thuộc danh mục được đánh dấu NVL vải lót
    lining_tmpl_ids = fields.Many2many(
        'product.template', 'product_template_lining_rel', 'product_tmpl_id', 'lining_tmpl_id',
        string='Vải lót', domain="[('categ_id.is_lining', '=', True)]")


class ProductProduct(models.Model):
    _inherit = "product.product"

    code_fabric = fields.Char(string='Mã vải')
    note = fields.Text(string='Ghi chú')


class ProductCategory(models.Model):
    _inherit = "product.category"

    is_lining = fields.Boolean(string='NVL vải lót', default=False)
