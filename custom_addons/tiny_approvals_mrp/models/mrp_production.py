from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .mrp_workorder import OPEN_REVIEW_STATES


class MrpWorkcenterProductivity(models.Model):
    _inherit = 'mrp.workcenter.productivity'

    work_type = fields.Selection([('new', 'Làm mới'), ('rework', 'Sửa')], string='Loại giờ',
                                 default='new', required=True, index=True)
    return_id = fields.Many2one('mrp.workorder.return', string='Lượt chỉnh', index=True, ondelete='set null')

    @api.model_create_multi
    def create(self, vals_list):
        # Mọi đường tạo phiên giờ (portal, backend, Shop Floor): công đoạn đang có lượt chỉnh mở thì là giờ sửa
        workorder_ids = {vals['workorder_id'] for vals in vals_list if vals.get('workorder_id')}
        if workorder_ids:
            workorders = self.env['mrp.workorder'].sudo().browse(list(workorder_ids))
            rework = {wo.id: wo.rework_return_id.id for wo in workorders if wo.rework_return_id}
            for vals in vals_list:
                return_id = rework.get(vals.get('workorder_id'))
                if return_id and 'work_type' not in vals:
                    vals['work_type'] = 'rework'
                    vals.setdefault('return_id', return_id)
        return super().create(vals_list)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    review_ids = fields.One2many('mrp.workorder.review', 'production_id', string='Lượt duyệt')
    return_ids = fields.One2many('mrp.workorder.return', 'production_id', string='Lượt trả lại')
    open_review_count = fields.Integer(string='Yêu cầu duyệt đang mở', compute='_compute_open_review_rework')
    rework_open_count = fields.Integer(string='Lượt chỉnh đang mở', compute='_compute_open_review_rework')
    has_open_review_or_rework = fields.Boolean(string='Còn duyệt / chỉnh đang mở',
                                               compute='_compute_open_review_rework')
    duration_new = fields.Float(string='Giờ làm mới (phút)', compute='_compute_review_durations', store=True)
    duration_rework = fields.Float(string='Giờ sửa (phút)', compute='_compute_review_durations', store=True)
    review_duration_total = fields.Float(string='Giờ duyệt (phút)', compute='_compute_review_durations', store=True)
    rework_count = fields.Integer(string='Số lượt chỉnh', compute='_compute_review_durations', store=True)

    @api.depends('review_ids.state', 'return_ids.state', 'workorder_ids.review_state')
    def _compute_open_review_rework(self):
        for production in self:
            production.open_review_count = len(production.review_ids.filtered(
                lambda r: r.state in OPEN_REVIEW_STATES))
            production.rework_open_count = len(production.return_ids.filtered(lambda r: r.state == 'open'))
            production.has_open_review_or_rework = bool(
                production.open_review_count or production.rework_open_count
                or any(wo.review_state == 'failed' for wo in production.workorder_ids if wo.state != 'cancel'))

    @api.depends('workorder_ids.duration_new', 'workorder_ids.duration_rework',
                 'review_ids.review_duration', 'return_ids.state')
    def _compute_review_durations(self):
        for production in self:
            production.duration_new = sum(production.workorder_ids.mapped('duration_new'))
            production.duration_rework = sum(production.workorder_ids.mapped('duration_rework'))
            production.review_duration_total = sum(production.review_ids.mapped('review_duration'))
            production.rework_count = len(production.return_ids.filtered(lambda r: r.state != 'cancel'))

    def _tiny_check_review_before_done(self):
        if self.env.context.get('skip_tiny_review_check'):
            return
        for production in self.filtered(lambda p: not p.is_mrp_pattern):
            if production.has_open_review_or_rework:
                pending = production.workorder_ids.filtered(
                    lambda wo: wo.state != 'cancel' and (
                        wo.rework_return_id or wo.review_state in OPEN_REVIEW_STATES + ('failed',)))
                raise UserError(_(
                    'Lệnh %(mo)s còn yêu cầu duyệt hoặc lượt chỉnh chưa xong (%(wos)s). '
                    'Phải xử lý hết trước khi xuất xưởng.',
                    mo=production.name, wos=', '.join(pending.mapped('name')) or '—'))

    def button_mark_done(self):
        self._tiny_check_review_before_done()
        return super().button_mark_done()

    def action_cancel(self):
        res = super().action_cancel()
        cancelled = self.filtered(lambda p: p.state == 'cancel')
        if cancelled:
            cancelled.workorder_ids._tiny_cancel_open_review_and_rework()
        return res
