import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def _default_user_stock(self):
        user = self.env['res.users'].search([('is_mrp_stock', '=', True)])
        return user

    user_mrp_stock_ids = fields.Many2many('res.users', 'user_mrp_stock_production_rel', string='Nhân viên kho',
                                          domain=[('is_mrp_stock', '=', True)], default=_default_user_stock)
