import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class MrpWorkcenterProductivity(models.Model):
    _inherit = "mrp.workcenter.productivity"

    user_mrp_id = fields.Many2one('res.users', string='Nhân viên MRP')

    @api.model_create_multi
    def create(self, vals_list):
        portal_user_id = self.env.context.get('portal_user_id')
        if portal_user_id:
            for vals in vals_list:
                if not vals.get('user_mrp_id'):
                    employee = self.env['hr.employee'].sudo().search([('user_id', '=', portal_user_id)], limit=1)
                    if employee:
                        vals['employee_id'] = employee.id
                    vals['user_mrp_id'] = portal_user_id
        return super().create(vals_list)
