import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    code_fabric = fields.Char(string='Mã vải')
    note = fields.Text(string='Ghi chú')


class ProductProduct(models.Model):
    _inherit = "product.product"

    code_fabric = fields.Char(string='Mã vải')
    note = fields.Text(string='Ghi chú')