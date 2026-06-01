import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    code = fields.Char(string='Mã')
