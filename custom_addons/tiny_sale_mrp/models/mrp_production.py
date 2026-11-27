from odoo import api, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    @api.depends('sale_line_id.order_id', 'reference_ids.sale_ids')
    def _compute_full_name(self):
        super()._compute_full_name()

    def _prepare_full_name(self):
        """Số lệnh/số đơn công ty thương mại + tên khách, ví dụ TNM/MO/000063/261112-OR-02 Cult Mia."""
        name = super()._prepare_full_name()
        sale_order = self._get_service_sale_order()
        if not sale_order:
            return name
        return ('%s/%s %s' % (name, sale_order.name, sale_order.partner_id.name or '')).strip()

    def _get_service_sale_order(self):
        """Đơn gốc ở công ty thương mại: SO công ty sản xuất -> PO (purchase_multi_origin) -> SO gốc.
        Không có PO thì lấy luôn SO của lệnh (bán trực tiếp ở công ty sản xuất)."""
        self.ensure_one()
        production = self.sudo()
        mrp_sale_order = production.sale_line_id.order_id or production.reference_ids.sale_ids[:1]
        if not mrp_sale_order or not mrp_sale_order.purchase_multi_origin:
            return mrp_sale_order
        purchase_order = self.env['purchase.order'].sudo().search(
            [('name', '=', mrp_sale_order.purchase_multi_origin)], limit=1)
        return purchase_order._get_sale_orders()[:1] or mrp_sale_order
