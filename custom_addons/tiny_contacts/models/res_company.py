from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time



class ResCompany(models.Model):
    _inherit = "res.company"

    is_mrp = fields.Boolean(string='Manufacturing Company', default=False)
    is_service = fields.Boolean(string='Trading Company', default=False)