import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    partner_code = fields.Char(string='Mã khách hàng', related='partner_id.code', store=True)
    ship_to = fields.Selection([('shop', 'Cửa hàng'), ('address_cus', 'Địa chỉ KH')], default='shop', string='Ship to')

    @api.model_create_multi
    def create(self, vals_list):
        # Mã đơn YYMMDD-OR-xx (thương mại) / YYMMDD-PO-xx (sản xuất), đánh số theo ngày đặt hàng
        for vals in vals_list:
            if vals.get('name', _("New")) != _("New"):
                continue
            company = self.env['res.company'].browse(vals.get('company_id')) if vals.get('company_id') else self.env.company
            if company.is_service:
                code = 'tiny.sale.order.service'
            elif company.is_mrp:
                code = 'tiny.sale.order.mrp'
            else:
                continue
            date_order = fields.Datetime.to_datetime(vals.get('date_order')) or fields.Datetime.now()
            seq_date = fields.Datetime.context_timestamp(self, date_order)
            name = self.env['ir.sequence'].with_company(company).next_by_code(code, sequence_date=seq_date)
            if name:
                vals['name'] = name
        return super().create(vals_list)

    def action_preview_sale_order(self):
        # Nút "Xem trước" mở mẫu in Tiny Ink dạng HTML thay cho trang portal
        self.ensure_one()
        return self.env.ref('tiny_sale.action_report_saleorder_preview').report_action(self, config=False)
