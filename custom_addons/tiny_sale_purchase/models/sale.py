import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    purchase_multi_origin = fields.Char(string='Origin purchase company service')

    def _action_confirm(self):
        result = super(SaleOrder, self)._action_confirm()
        if self.company_id.is_service:
            purchase_orders = self._get_purchase_orders()
            for order in purchase_orders:
                order.button_confirm()

        return result

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # def _purchase_service_create(self, quantity=False):
    #     res = super()._purchase_service_create(quantity=quantity)
    #     print("res", res)
    #     return res
        
