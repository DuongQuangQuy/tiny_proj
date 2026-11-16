import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    mrp_production_id = fields.Many2one('mrp.production', string='Manufacturing Order')

    def action_view_mrp_production(self):
        """Smart button: mở lệnh sản xuất của phiếu phê duyệt."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Manufacturing Order'),
            'res_model': 'mrp.production',
            'view_mode': 'form',
            'res_id': self.mrp_production_id.id,
        }
