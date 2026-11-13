from odoo import api, fields, models

REVIEW_POLICY = [
    ('none', 'Không có điểm duyệt'),
    ('required', 'Bắt buộc duyệt'),
    ('optional', 'Quản lý chọn'),
]
REVIEW_MODE = [
    ('before', 'Kiểm trước'),
    ('after', 'Kiểm sau'),
    ('none', 'Không yêu cầu kiểm'),
]


class MrpReason(models.Model):
    _inherit = 'mrp.reason'

    reason_type = fields.Selection([
        ('pause', 'Tạm dừng'),
        ('defect', 'Lỗi'),
        ('return', 'Trả lại'),
    ], string='Loại', default='pause', required=True)


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    review_policy = fields.Selection(REVIEW_POLICY, string='Điểm duyệt', default='none', required=True)
    default_review_mode = fields.Selection(REVIEW_MODE, string='Chế độ kiểm mặc định', default='before',
                                           help='Chỉ dùng khi điểm duyệt là "Quản lý chọn".')
    user_review_ids = fields.Many2many('res.users', 'mrp_workcenter_user_review_rel', 'workcenter_id', 'user_id',
                                       string='Quản lý duyệt')


class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'

    review_policy = fields.Selection(REVIEW_POLICY, string='Điểm duyệt', compute='_compute_review_config',
                                     store=True, readonly=False)
    default_review_mode = fields.Selection(REVIEW_MODE, string='Chế độ kiểm mặc định',
                                           compute='_compute_review_config', store=True, readonly=False)
    user_review_ids = fields.Many2many('res.users', 'mrp_routing_workcenter_user_review_rel', 'operation_id', 'user_id',
                                       string='Quản lý duyệt', compute='_compute_review_config',
                                       store=True, readonly=False)

    @api.depends('workcenter_id.review_policy', 'workcenter_id.default_review_mode',
                 'workcenter_id.user_review_ids')
    def _compute_review_config(self):
        for record in self:
            record.review_policy = record.workcenter_id.review_policy or 'none'
            record.default_review_mode = record.workcenter_id.default_review_mode or 'before'
            record.user_review_ids = record.workcenter_id.user_review_ids


class ResUsers(models.Model):
    _inherit = 'res.users'

    is_mrp_reviewer = fields.Boolean(string='Là người duyệt công đoạn', compute='_compute_is_mrp_reviewer')

    def _compute_is_mrp_reviewer(self):
        Workorder = self.env['mrp.workorder'].sudo()
        for user in self:
            user.is_mrp_reviewer = bool(Workorder.search_count([('user_review_ids', 'in', user.id)], limit=1))
