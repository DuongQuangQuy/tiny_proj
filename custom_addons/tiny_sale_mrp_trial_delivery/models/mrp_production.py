# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    trial_delivery_ids = fields.One2many(
        'trial.delivery',
        'production_id',
        string='Trial Delivery',
    )
    trial_delivery_count = fields.Integer(
        string='Trial Delivery Number',
        compute='_compute_trial_delivery_count',
    )

    # Thử hàng (Fitting) chọn trên đơn bán gốc ở công ty thương mại, không lưu: luôn theo đơn gốc
    trial_id = fields.Many2one('sale.trial', string='Fitting', compute='_compute_trial_id')

    @api.depends('trial_delivery_ids')
    def _compute_trial_delivery_count(self):
        for prod in self:
            prod.trial_delivery_count = len(prod.trial_delivery_ids)

    @api.depends('sale_line_id', 'reference_ids')
    def _compute_trial_id(self):
        for prod in self:
            trial = self.env['sale.trial']
            try:
                # _get_service_sale_order (tiny_sale_mrp): SO cty sản xuất -> PO -> SO gốc, có xét cả reference_ids
                trial = prod._get_service_sale_order().sudo().trial_id
            except Exception:
                _logger.exception('Could not get fitting of manufacturing order %s', prod.id)
            prod.trial_id = trial.id

    def _is_fitting_workcenter(self, workcenter):
        """Khu vực sản xuất có phải nơi thử hàng của lệnh không. Fitting có thể chọn khu vực của công ty
        thương mại, khu vực 2 công ty nối với nhau bằng mã (mrp.workcenter.code) nên so cả mã."""
        self.ensure_one()
        fitting_wc = self.trial_id.sudo().workcenter_id
        if not fitting_wc or not workcenter:
            return False
        if fitting_wc == workcenter:
            return True
        return bool(fitting_wc.code) and fitting_wc.code == workcenter.sudo().code

    def _get_origin_sale_order(self):
        """Truy ngược đơn hàng gốc thực sự (ở công ty dịch vụ) của lệnh sản xuất.

        Luồng: SO (cty dịch vụ, khách hàng thật)
            -> PO (cty dịch vụ, tạo tự động qua route MTO+Mua)
            -> SO (cty sản xuất, được tạo bởi _create_sale_company_mrp,
                   partner_id = công ty dịch vụ, không phải khách hàng thật)
            -> MO (cty sản xuất, self.sale_line_id.order_id trỏ tới SO ở trên)

        Từ MO ta đi ngược lại: sale_line_id.order_id (cty sản xuất)
            -> purchase.order có sale_multi_origin = tên SO đó (cty dịch vụ)
            -> purchase.order._get_sale_orders() trả về SO gốc (cty dịch vụ, khách hàng thật)

        Lưu ý: mrp.production không có field sale_order_id, chỉ có sale_line_id
        (Many2one sale.order.line, do module sale_mrp thêm vào).
        """
        self.ensure_one()
        mrp_sale_order = self.sale_line_id.order_id
        if not mrp_sale_order:
            return self.env['sale.order']
        purchase_order = self.env['purchase.order'].sudo().search([
            ('sale_multi_origin', '=', mrp_sale_order.name),
        ], limit=1)
        if not purchase_order:
            return mrp_sale_order
        origin_sale_orders = purchase_order.sudo()._get_sale_orders()
        return origin_sale_orders[:1] if origin_sale_orders else mrp_sale_order

    def action_create_trial_delivery(self):
        """Tạo phiếu giao hàng thử từ lệnh sản xuất"""
        self.ensure_one()
        origin_sale_order = self._get_origin_sale_order()
        ctx = {
            'default_production_id': self.id,
            'default_partner_id': origin_sale_order.partner_id.id if origin_sale_order else False,
            'default_sale_origin': origin_sale_order.name if origin_sale_order else False,
            'default_trial_id': self.trial_id.id,
            'default_line_ids': [(0, 0, {
                'product_id': self.product_id.id,
                'qty_trial': self.product_qty,
                'product_uom_id': self.product_uom_id.id,
            })],
        }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Trial Delivery'),
            'res_model': 'trial.delivery',
            'view_mode': 'form',
            'context': ctx,
            'target': 'current',
        }

    def action_view_trial_deliveries(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Trial Delivery'),
            'res_model': 'trial.delivery',
            'view_mode': 'list,form',
            'domain': [('production_id', '=', self.id)],
        }
        if self.trial_delivery_count == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.trial_delivery_ids[0].id
        return action
