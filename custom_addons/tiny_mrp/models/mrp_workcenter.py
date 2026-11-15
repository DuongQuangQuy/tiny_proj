import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    user_mrp_ids = fields.Many2many('res.users', 'mrp_workcenter_user_mrp_rel', string='Operators')
    is_pattern = fields.Boolean(string='Pattern Work Center', default=False,
                                help='Work orders at this work center are pattern work orders and must be done before the others.')
    estimate_time = fields.Float(
        string='Estimated Time',
        help='Minutes to make 1 product at this work center. When this work center is selected on a BoM operation, '
             'this value fills the Default Duration (editable). Leave 0 to keep the current duration.')
