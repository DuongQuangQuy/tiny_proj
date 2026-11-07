import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    # Danh sách vải lót được phép chọn trên dòng NVL vải lót (theo vải có setup Vải lót)
    lining_product_ids = fields.Many2many('product.product', compute='_compute_lining_product_ids',
                                          string='Vải lót được phép')

    @api.depends('move_raw_ids.product_id')
    def _compute_lining_product_ids(self):
        for production in self:
            lining_tmpls = production.move_raw_ids.product_id.product_tmpl_id.lining_tmpl_ids
            if lining_tmpls:
                production.lining_product_ids = lining_tmpls.product_variant_ids
            else:
                production.lining_product_ids = self.env['product.product'].search(
                    [('categ_id.is_lining', '=', True)])

    def _default_user_stock(self):
        return self.env['res.users'].search(['|', ('is_mrp_stock', '=', True), ('is_mrp_pattern', '=', True)])

    user_mrp_stock_ids = fields.Many2many('res.users', 'user_mrp_stock_production_rel', string='Nhân viên kho',
                                           default=_default_user_stock)

    # Lệnh rập phụ kiểu cũ (MO con). Quy trình mới dùng công đoạn rập, trường này chỉ giữ cho dữ liệu cũ.
    is_mrp_pattern = fields.Boolean(string='Là MRP rập', default=False)
    state_stock = fields.Selection([('draft', 'Nháp'),
        ('confirmed', 'Xác nhận'),
        ('cancel', 'Đã hủy')
    ], string='Trạng thái MRP kho', default='draft')
    state_pattern = fields.Selection([('draft', 'Nháp'),
        ('confirmed', 'Xác nhận'),
        ('cancel', 'Đã hủy')
    ], string='Trạng thái MRP rập', default='draft')
    has_pattern_workorder = fields.Boolean(string='Có công đoạn rập', compute='_compute_pattern_workorders')
    pattern_workorders_done = fields.Boolean(string='Rập đã xong', compute='_compute_pattern_workorders')
    need_pattern_confirm = fields.Boolean(string='Cần xác nhận rập', compute='_compute_pattern_workorders')

    @api.depends('workorder_ids.is_pattern', 'workorder_ids.state')
    def _compute_pattern_workorders(self):
        for production in self:
            pattern_wos = production.workorder_ids.filtered('is_pattern')
            production.has_pattern_workorder = bool(pattern_wos)
            production.pattern_workorders_done = all(wo.state in ('done', 'cancel') for wo in pattern_wos)
            production.need_pattern_confirm = bool(pattern_wos) or bool(production._get_children())

    def action_confirm_pattern(self):
        """Nhân viên rập xác nhận đã nhập xong số lượng NVL sau khi công đoạn rập hoàn thành."""
        for production in self:
            if production.state not in ('confirmed', 'progress'):
                raise UserError(_('Lệnh sản xuất chưa được xác nhận, không thể xác nhận rập.'))
            if not production.pattern_workorders_done:
                raise UserError(_('Công đoạn rập chưa hoàn thành.'))
            production.state_pattern = 'confirmed'

    def action_confirm_stock(self):
        for production in self:
            if production.state == 'draft':
                raise UserError(_('Lệnh sản xuất chưa được xác nhận, không thể xác nhận kho.'))
            # Lệnh không có công đoạn rập (hay lệnh rập con kiểu cũ) thì không có bước xác nhận rập
            if production.need_pattern_confirm and production.state_pattern != 'confirmed':
                raise UserError(_('Chỉ có thể xác nhận kho khi rập và số lượng NVL đã được xác nhận.'))
            production.state_stock = 'confirmed'

    def action_done_pattern(self):
        for production in self:
            if not production.is_mrp_pattern:
                raise UserError(_('Chỉ có thể hoàn thành lệnh rập.'))
            if production.state in ('done', 'cancel'):
                raise UserError(_('Lệnh sản xuất đã hoàn thành hoặc bị hủy.'))
            production.with_context(skip_immediate=True, skip_backorder=True).button_mark_done()

    @api.model_create_multi
    def create(self, vals_list):
        productions = super().create(vals_list)
        productions._apply_matching_zipper()
        return productions

    def write(self, vals):
        res = super().write(vals)
        if {'move_raw_ids', 'bom_id', 'product_id'} & set(vals):
            self._apply_matching_zipper()
        return res

    def _apply_matching_zipper(self):
        """Thay NVL dây kéo theo màu dây kéo liên kết với vải, giữ biến thể (ngắn/dài) theo BOM."""
        for production in self.filtered(lambda p: p.state == 'draft'):
            raws = production.move_raw_ids.filtered(lambda m: m.state == 'draft')
            fabric = raws.product_id.filtered('matching_zipper_tmpl_id')[:1]
            if not fabric:
                continue
            variants = fabric.matching_zipper_tmpl_id.product_variant_ids
            for move in raws.filtered(lambda m: m.product_id.is_zipper):
                attr_values = move.product_id.product_template_attribute_value_ids.product_attribute_value_id
                new_zipper = variants.filtered(
                    lambda p: p.product_template_attribute_value_ids.product_attribute_value_id == attr_values)[:1]
                if new_zipper and new_zipper != move.product_id:
                    move.product_id = new_zipper

    def action_confirm(self):
        self._apply_matching_zipper()
        return super().action_confirm()
