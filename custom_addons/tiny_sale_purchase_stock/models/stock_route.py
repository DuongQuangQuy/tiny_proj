import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class StockRoute(models.Model):
    _inherit = "stock.route"

    is_mrp = fields.Boolean(string='Là sản xuất')
