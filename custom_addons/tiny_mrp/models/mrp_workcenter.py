import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time

_logger = logging.getLogger(__name__)


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    user_mrp_ids = fields.Many2many('res.users', 'mrp_workcenter_user_mrp_rel', string='Nhân viên thực hiện')
    is_pattern = fields.Boolean(string='Khu vực rập', default=False,
                                help='Công đoạn tại khu vực này là công đoạn rập, phải làm trước các công đoạn khác.')
    estimate_time = fields.Float(
        string='Thời gian dự kiến',
        help='Số phút để làm 1 sản phẩm tại khu vực này. Khi chọn khu vực trên hoạt động của BOM, '
             'giá trị này điền sẵn vào Thời lượng mặc định (sửa được). Để 0 thì giữ nguyên thời lượng đang có.')
