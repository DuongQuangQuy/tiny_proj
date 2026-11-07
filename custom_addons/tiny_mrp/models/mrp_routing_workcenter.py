from odoo import api, fields, models


class MrpRoutingWorkcenter(models.Model):
    _inherit = "mrp.routing.workcenter"

    # Công đoạn rập: luôn phải làm xong trước, sau đó nhập NVL, kho xác nhận rồi mới làm các công đoạn khác
    is_pattern = fields.Boolean(string='Công đoạn rập', compute='_compute_is_pattern', store=True, readonly=False,
                                help='Lấy theo khu vực sản xuất, có thể sửa riêng trên từng công đoạn. '
                                     'Công đoạn rập luôn được thực hiện trước. Các công đoạn khác chỉ được bắt đầu '
                                     'khi rập đã xong, đã xác nhận NVL rập và kho đã xác nhận.')

    @api.depends('workcenter_id.is_pattern')
    def _compute_is_pattern(self):
        for record in self:
            record.is_pattern = record.workcenter_id.is_pattern
