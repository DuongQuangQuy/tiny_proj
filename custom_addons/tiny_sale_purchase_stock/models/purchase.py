import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def vals_lines_so_multi(self):
        res = super().vals_lines_so_multi()
        route = self.env['stock.route'].search([('is_mrp', '=', True)], limit=1)
        res.update({
            'route_ids': route.ids,
        })
        return res