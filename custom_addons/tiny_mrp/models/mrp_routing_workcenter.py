from odoo import fields, models


class MrpRoutingWorkcenter(models.Model):
    _inherit = "mrp.routing.workcenter"

    # Công đoạn rập: luôn phải làm xong trước, sau đó nhập NVL, kho xác nhận rồi mới làm các công đoạn khác
    is_pattern = fields.Boolean(string='Công đoạn rập', default=False,
                                help='Công đoạn rập luôn được thực hiện trước. Các công đoạn khác chỉ được bắt đầu '
                                     'khi rập đã xong, đã xác nhận NVL rập và kho đã xác nhận.')
