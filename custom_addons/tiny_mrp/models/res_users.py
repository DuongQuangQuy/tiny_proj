import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)



class ResUsers(models.Model):
    _inherit = "res.users"

    is_mrp_pattern = fields.Boolean(string='Is Pattern MRP Staff', default=False)
    is_mrp_stock = fields.Boolean(string='Is MRP Warehouse Staff', default=False)