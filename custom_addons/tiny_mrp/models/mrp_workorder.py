import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    user_mrp_ids = fields.Many2many('res.users', 'mrp_workorder_user_mrp_rel', string='Nhân viên thực hiện',compute='_compute_user_mrp_ids',store=True,readonly=False)

    @api.depends('workcenter_id','workcenter_id.user_mrp_ids')
    def _compute_user_mrp_ids(self):
        for record in self:
            if record.workcenter_id:
                record.user_mrp_ids = record.workcenter_id.user_mrp_ids if record.workcenter_id.user_mrp_ids else None
            else:
                record.user_mrp_ids = None

    def _should_start_timer(self):
        if self.env.context.get('portal_user_id'):
            return True
        return super()._should_start_timer()
