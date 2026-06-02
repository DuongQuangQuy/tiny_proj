import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    sale_multi_origin = fields.Char(string='Origin sale company mrp')

    def button_confirm(self):
        res = super().button_confirm()
        for rec in self:
            if rec.company_id.is_service and bool(rec._get_sale_orders()):
                manufacturing_so = rec._create_sale_company_mrp()
                if manufacturing_so:
                    rec.sale_multi_origin = manufacturing_so.name
        return res

    def _create_sale_company_mrp(self):
        """Tạo Sale Order cho công ty sản xuất (is_mrp = True)"""
        self.ensure_one()
        mrp_company = self.env['res.company'].sudo().search([('is_mrp', '=', True)], limit=1)
        if not mrp_company:
            return
        customer = self.company_id.partner_id
        if not customer:
            return
        so_vals = {
            'partner_id': customer.id,
            'company_id': mrp_company.id,
            'currency_id': self.currency_id.id,
            'date_order': fields.Datetime.now(),
            'origin': self.name,
            'purchase_multi_origin': self.name,
            'order_line': [],
        }
        for po_line in self.order_line:
            so_line_vals = {
                'product_id': po_line.product_id.id,
                'name': po_line.name,
                'product_uom_qty': po_line.product_qty,
                'product_uom_id': po_line.product_uom_id.id,
                'price_unit': po_line.price_unit,

            }
            sale_lines = po_line.sudo().sale_line_id or po_line.move_dest_ids.mapped('sale_line_id')
            if sale_lines:
                sale_line = sale_lines[0]
                so_line_vals.update({
                    'image_128': sale_line.image_128,
                    'product_size': sale_line.product_size,
                    'note': sale_line.note,
                    'default_code': sale_line.default_code,
                    'product_pattern_id': sale_line.product_pattern_id.id,
                    'product_pattern_image': sale_line.product_pattern_image,
                    'note_pattern': sale_line.note_pattern,
                })
            so_vals['order_line'].append((0, 0, so_line_vals))

        manufacturing_so = self.env['sale.order'].with_company(mrp_company).sudo().create(so_vals)

        return manufacturing_so
