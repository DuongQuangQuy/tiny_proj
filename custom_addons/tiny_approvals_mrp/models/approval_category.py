import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class ApprovalCategory(models.Model):
    _inherit = "approval.category"

    approval_type = fields.Selection(
        selection_add=[('mrp_stock', "Phê duyệt kho MRP")],
        ondelete={'mrp_stock': "cascade"})

    @api.onchange('approval_type')
    def _onchange_approval_type(self):
        res = super()._onchange_approval_type()
        if self.approval_type == 'mrp_stock':
            self.has_product = 'required'
            self.has_quantity = 'required'
            # self.has_location = 'required'
        return res