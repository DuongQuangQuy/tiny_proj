import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    user_mrp_ids = fields.Many2many('res.users', 'mrp_workorder_user_mrp_rel', string='Nhân viên thực hiện',
                                    compute='_compute_user_mrp_ids', store=True, readonly=False)
    reason_ids = fields.One2many('mrp.pause.reason', 'workorder_id', string='Lý do tạm dừng')
    is_pattern = fields.Boolean(string='Công đoạn rập', compute='_compute_is_pattern', store=True, readonly=False)

    @api.depends('workcenter_id', 'workcenter_id.user_mrp_ids')
    def _compute_user_mrp_ids(self):
        for record in self:
            record.user_mrp_ids = record.workcenter_id.user_mrp_ids

    @api.depends('operation_id.is_pattern', 'workcenter_id.is_pattern')
    def _compute_is_pattern(self):
        for record in self:
            # Work order thêm tay không có công đoạn BOM thì lấy theo khu vực sản xuất
            record.is_pattern = (record.operation_id or record.workcenter_id).is_pattern

    def _get_flow_block_reason(self):
        """Lý do công đoạn này chưa được phép bắt đầu theo quy trình rập -> NVL -> kho, hoặc False."""
        self.ensure_one()
        if self.is_pattern:
            return False
        production = self.production_id
        if production.is_mrp_pattern:
            # Lệnh rập phụ kiểu cũ: giữ nguyên cách chạy trước đây
            return False
        if not production.pattern_workorders_done:
            return _('Công đoạn rập chưa hoàn thành.')
        if production.need_pattern_confirm and production.state_pattern != 'confirmed':
            return _('Chưa xác nhận số lượng NVL sau rập.')
        if production.state_stock != 'confirmed':
            return _('Kho chưa xác nhận.')
        return False

    def button_start(self, *args, **kwargs):
        for workorder in self:
            reason = workorder._get_flow_block_reason()
            if reason:
                raise UserError(_('Không thể bắt đầu công đoạn "%(name)s": %(reason)s',
                                  name=workorder.name, reason=reason))
        return super().button_start(*args, **kwargs)

    def _should_start_timer(self):
        if self.env.context.get('portal_user_id'):
            return True
        return super()._should_start_timer()
