from odoo import api, fields, models


class MrpRoutingWorkcenter(models.Model):
    _inherit = "mrp.routing.workcenter"

    # Công đoạn rập: luôn phải làm xong trước, sau đó nhập NVL, kho xác nhận rồi mới làm các công đoạn khác
    is_pattern = fields.Boolean(string='Pattern Work Order', compute='_compute_is_pattern', store=True, readonly=False,
                                help='Taken from the work center and can be changed on each operation. The pattern work order is always done first. Other work orders can only start once the pattern is done, the pattern materials are confirmed and the warehouse has confirmed.')

    @api.depends('workcenter_id.is_pattern')
    def _compute_is_pattern(self):
        for record in self:
            record.is_pattern = record.workcenter_id.is_pattern

    @api.onchange('workcenter_id')
    def _onchange_workcenter_id_estimate_time(self):
        """Điền Thời lượng mặc định theo Thời gian dự kiến của khu vực, nếu khu vực có khai báo."""
        for record in self:
            if record.workcenter_id.estimate_time:
                record.time_cycle_manual = record.workcenter_id.estimate_time
