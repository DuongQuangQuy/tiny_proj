import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

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
            production.state_stock = 'confirmed'

    def action_done_pattern(self):
        for production in self:
            if not production.is_mrp_pattern:
                raise UserError(_('Chỉ có thể hoàn thành lệnh rập.'))
            if production.state in ('done', 'cancel'):
                raise UserError(_('Lệnh sản xuất đã hoàn thành hoặc bị hủy.'))
            production.with_context(skip_immediate=True, skip_backorder=True).button_mark_done()

    def action_confirm(self):
        productions = super().action_confirm()
        for production in self:
            mrp_production_childs = production._get_children()
            if mrp_production_childs:
                for mrp_production_child in mrp_production_childs:
                    mrp_production_child.is_mrp_pattern = True
                    user_pattern = self.env['res.users'].search([('is_mrp_pattern', '=', True)])
                    mrp_production_child.user_mrp_stock_ids = [(6, 0, user_pattern.ids)]
        return productions