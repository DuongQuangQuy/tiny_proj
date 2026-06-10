import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_print_so(self):
        self.ensure_one()
        sale_order = self.env['sale.order'].search([('invoice_ids', 'in', self.ids)])
        if sale_order:
            return self.env.ref('sale.action_report_saleorder').report_action(sale_order.ids)
        return True
