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
