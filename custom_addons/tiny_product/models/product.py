import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Mã vải = sản phẩm NVL thuộc danh mục được đánh dấu "NVL vải chính" (trước đây là ô chữ)
    code_fabric = fields.Many2one(
        'product.product', string='Mã vải', domain="[('categ_id.is_main_fabric', '=', True)]")
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

    def write(self, vals):
        if 'code_fabric' not in vals:
            return super().write(vals)
        # Đổi mã vải trên template: chỉ cập nhật biến thể đang theo template (trống hoặc bằng mã cũ),
        # biến thể đã sửa riêng thì giữ nguyên
        old_fabric = {tmpl.id: tmpl.code_fabric.id for tmpl in self}
        res = super().write(vals)
        for tmpl in self:
            variants = tmpl.with_context(active_test=False).product_variant_ids.filtered(
                lambda v: not v.code_fabric or v.code_fabric.id == old_fabric[tmpl.id])
            if variants:
                variants.write({'code_fabric': tmpl.code_fabric.id})
        return res


class ProductProduct(models.Model):
    _inherit = "product.product"

    # Mã vải riêng của biến thể: mặc định lấy theo template khi tạo, sửa riêng được
    code_fabric = fields.Many2one(
        'product.product', string='Mã vải', domain="[('categ_id.is_main_fabric', '=', True)]",
        compute='_compute_code_fabric', store=True, readonly=False, precompute=True)
    note = fields.Text(string='Ghi chú')

    @api.depends('product_tmpl_id')
    def _compute_code_fabric(self):
        # Chỉ điền khi biến thể chưa có mã; đổi mã trên template được xử lý trong ProductTemplate.write
        for variant in self:
            if not variant.code_fabric:
                variant.code_fabric = variant.product_tmpl_id.code_fabric


class ProductCategory(models.Model):
    _inherit = "product.category"

    is_lining = fields.Boolean(string='NVL vải lót', default=False)
    is_main_fabric = fields.Boolean(string='Main Fabric Material', default=False)
