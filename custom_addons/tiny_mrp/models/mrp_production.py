import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

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
        user_stock = self.env['res.users'].search([('is_mrp_stock', '=', True)])
        user_pattern = self.env['res.users'].search([('is_mrp_pattern', '=', True)])
        user = user_stock | user_pattern
        return user

    user_mrp_stock_ids = fields.Many2many('res.users', 'user_mrp_stock_production_rel', string='Nhân viên kho',
                                           default=_default_user_stock)

    is_mrp_pattern = fields.Boolean(string='Là MRP rập', default=False)
    state_stock = fields.Selection([('draft', 'Nháp'),
        ('confirmed', 'Xác nhận'),
        ('cancel', 'Đã hủy')
    ], string='Trạng thái MRP kho', default='draft')
    state_pattern = fields.Selection([('draft', 'Nháp'),
        ('confirmed', 'Xác nhận'),
        ('cancel', 'Đã hủy')
    ], string='Trạng thái MRP rập', default='draft')    

    # @api.model_create_multi
    # def create(self, vals_list):
    #     productions = super().create(vals_list)
    #     mrp_production_ids = self._get_sources()
    #
    #     return productions

    def action_confirm_pattern(self):
        for production in self:
            mrp_production_childs = production._get_children()
            if mrp_production_childs:
                childs_not_done = mrp_production_childs.filtered(lambda p: p.state != 'done')
                if childs_not_done:
                    raise UserError(_('Các lệnh sản xuất con chưa hoàn thành.'))
            production.state_pattern = 'confirmed'
    
    def action_confirm_stock(self):
        for production in self:
            if production.state == 'draft':
                raise UserError(_('Lệnh sản xuất chưa được xác nhận, không thể xác nhận kho.'))
            # Lệnh không có lệnh con (lệnh rập) thì không có bước xác nhận rập
            if production._get_children() and production.state_pattern != 'confirmed':
                raise UserError(_('Chỉ có thể xác nhận lệnh sản xuất kho khi lệnh rập đã được xác nhận.'))
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
        productions = super().action_confirm()
        for production in self:
            mrp_production_childs = production._get_children()
            if mrp_production_childs:
                for mrp_production_child in mrp_production_childs:
                    mrp_production_child.is_mrp_pattern = True
                    user_pattern = self.env['res.users'].search([('is_mrp_pattern', '=', True)])
                    mrp_production_child.user_mrp_stock_ids = [(6, 0, user_pattern.ids)]
        return productions