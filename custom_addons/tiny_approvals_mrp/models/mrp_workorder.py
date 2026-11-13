from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .mrp_review_config import REVIEW_MODE, REVIEW_POLICY

REVIEW_STATE = [
    ('no', 'Không duyệt'),
    ('waiting', 'Chờ duyệt'),
    ('reviewing', 'Đang duyệt'),
    ('paused', 'Tạm dừng duyệt'),
    ('passed', 'Đạt'),
    ('failed', 'Chưa đạt'),
]
OPEN_REVIEW_STATES = ('waiting', 'reviewing', 'paused')


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    # ---------- Cấu hình điểm duyệt ----------
    review_policy = fields.Selection(REVIEW_POLICY, string='Điểm duyệt', compute='_compute_review_policy', store=True)
    review_mode = fields.Selection(REVIEW_MODE, string='Chế độ kiểm', compute='_compute_review_mode',
                                   store=True, readonly=False, copy=False)
    review_mode_user_id = fields.Many2one('res.users', string='Người chọn chế độ kiểm', readonly=True, copy=False)
    review_mode_date = fields.Datetime(string='Thời điểm chọn chế độ kiểm', readonly=True, copy=False)
    user_review_ids = fields.Many2many('res.users', 'mrp_workorder_user_review_rel', 'workorder_id', 'user_id',
                                       string='Quản lý duyệt', compute='_compute_user_review_ids',
                                       store=True, readonly=False)
    can_edit_review_mode = fields.Boolean(string='Được chọn chế độ kiểm', compute='_compute_can_edit_review_mode')

    # ---------- Lượt duyệt ----------
    review_ids = fields.One2many('mrp.workorder.review', 'workorder_id', string='Lượt duyệt')
    last_review_id = fields.Many2one('mrp.workorder.review', string='Lượt duyệt mới nhất',
                                     compute='_compute_last_review_id')
    review_state = fields.Selection(REVIEW_STATE, string='Trạng thái duyệt', compute='_compute_review_state',
                                    store=True)

    # ---------- Trả lại / chỉnh lại ----------
    rework_return_id = fields.Many2one('mrp.workorder.return', string='Lượt chỉnh đang mở', copy=False, readonly=True)
    return_ids = fields.One2many('mrp.workorder.return', 'workorder_id', string='Lượt chỉnh')
    rework_count = fields.Integer(string='Số lượt chỉnh', compute='_compute_rework_count', store=True)

    # ---------- Thời gian làm mới / sửa ----------
    duration_new = fields.Float(string='Giờ làm mới (phút)', compute='_compute_duration_split', store=True)
    duration_rework = fields.Float(string='Giờ sửa (phút)', compute='_compute_duration_split', store=True)

    @api.depends('operation_id.review_policy', 'workcenter_id.review_policy')
    def _compute_review_policy(self):
        for record in self:
            # Work order thêm tay không có công đoạn BOM thì lấy theo khu vực sản xuất
            record.review_policy = (record.operation_id or record.workcenter_id).review_policy or 'none'

    @api.depends('review_policy', 'operation_id.default_review_mode', 'workcenter_id.default_review_mode')
    def _compute_review_mode(self):
        for record in self:
            if record.state in ('done', 'cancel') and record.review_mode:
                # Không đổi chế độ kiểm của công đoạn đã kết thúc khi sửa cấu hình khu vực
                continue
            if record.review_policy == 'required':
                record.review_mode = 'before'
            elif record.review_policy == 'optional':
                record.review_mode = (record.operation_id or record.workcenter_id).default_review_mode or 'before'
            else:
                record.review_mode = 'none'

    @api.depends('operation_id.user_review_ids', 'workcenter_id.user_review_ids')
    def _compute_user_review_ids(self):
        for record in self:
            record.user_review_ids = (record.operation_id or record.workcenter_id).user_review_ids

    @api.depends_context('uid')
    @api.depends('review_policy', 'state', 'user_review_ids')
    def _compute_can_edit_review_mode(self):
        for record in self:
            record.can_edit_review_mode = (
                record.review_policy == 'optional'
                and record.state not in ('done', 'cancel')
                and record._tiny_is_reviewer()
            )

    def _tiny_last_review(self):
        self.ensure_one()
        reviews = self.review_ids.filtered(lambda r: r.state != 'cancel')
        return reviews.sorted(lambda r: (r.round_no, r.id))[-1:]

    @api.depends('review_ids.state', 'review_ids.round_no')
    def _compute_last_review_id(self):
        for record in self:
            record.last_review_id = record._tiny_last_review()

    @api.depends('review_ids.state', 'review_ids.round_no')
    def _compute_review_state(self):
        for record in self:
            last = record._tiny_last_review()
            record.review_state = last.state if last else 'no'

    @api.depends('return_ids.state')
    def _compute_rework_count(self):
        for record in self:
            record.rework_count = len(record.return_ids.filtered(lambda r: r.state != 'cancel'))

    @api.depends('time_ids.duration', 'time_ids.work_type')
    def _compute_duration_split(self):
        for record in self:
            record.duration_new = sum(record.time_ids.filtered(lambda t: t.work_type != 'rework').mapped('duration'))
            record.duration_rework = sum(record.time_ids.filtered(lambda t: t.work_type == 'rework').mapped('duration'))

    # ------------------------------------------------------------------
    # Quyền
    # ------------------------------------------------------------------
    def _tiny_is_reviewer(self, check_user=None):
        """Người dùng là quản lý sản xuất hoặc có trong danh sách quản lý duyệt của công đoạn."""
        check_user = check_user or self.env.user
        return check_user.has_group('mrp.group_mrp_manager') or any(
            check_user in wo.user_review_ids for wo in self)

    def _tiny_check_reviewer(self, check_user=None):
        for workorder in self:
            if not workorder._tiny_is_reviewer(check_user):
                raise UserError(_('Bạn không phải quản lý duyệt của công đoạn "%s".', workorder.name))

    # ------------------------------------------------------------------
    # Ghi chế độ kiểm
    # ------------------------------------------------------------------
    def write(self, vals):
        if 'review_mode' in vals and not self.env.context.get('tiny_skip_review_mode_check'):
            changed = self.filtered(lambda wo: wo.review_mode != vals['review_mode'])
            for workorder in changed:
                if workorder.review_policy == 'required':
                    raise UserError(_('Công đoạn "%s" bắt buộc duyệt, không đổi được chế độ kiểm.', workorder.name))
                if workorder.review_policy == 'none':
                    raise UserError(_('Công đoạn "%s" không có điểm duyệt.', workorder.name))
                if workorder.state in ('done', 'cancel'):
                    raise UserError(_('Công đoạn "%s" đã kết thúc, không đổi được chế độ kiểm.', workorder.name))
            changed._tiny_check_reviewer()
            if changed:
                res = super().write(vals)
                super(MrpWorkorder, changed).write({
                    'review_mode_user_id': self.env.user.id,
                    'review_mode_date': fields.Datetime.now(),
                })
                return res
        return super().write(vals)

    # ------------------------------------------------------------------
    # Thứ tự công đoạn
    # ------------------------------------------------------------------
    def _tiny_sort_key(self):
        return (self.sequence, self.id)

    def _tiny_get_previous_workorders(self):
        """Các công đoạn ngay trước: theo phụ thuộc nếu có, ngược lại là mọi công đoạn cùng lệnh đứng trước."""
        self.ensure_one()
        if self.blocked_by_workorder_ids:
            return self.blocked_by_workorder_ids.filtered(lambda wo: wo.state != 'cancel')
        key = self._tiny_sort_key()
        return self.production_id.workorder_ids.filtered(
            lambda wo: wo.state != 'cancel' and wo._tiny_sort_key() < key)

    def _tiny_get_all_previous_workorders(self):
        """Tất cả công đoạn đứng trước (theo phụ thuộc thì lấy đệ quy)."""
        self.ensure_one()
        result = self.browse()
        todo = self._tiny_get_previous_workorders()
        while todo:
            result |= todo
            todo = todo.browse([p.id for wo in todo for p in wo._tiny_get_previous_workorders()]) - result
        return result

    def _get_flow_block_reason(self):
        self.ensure_one()
        production = self.production_id
        if production.is_mrp_pattern:
            return super()._get_flow_block_reason()
        if not self.rework_return_id:
            # Đang chỉnh lại thì các bước rập / kho đã qua từ trước, không xét lại
            reason = super()._get_flow_block_reason()
            if reason:
                return reason
        # Xét mọi công đoạn đứng trước (Odoo nối công đoạn thành chuỗi phụ thuộc nên phải lấy đệ quy)
        for previous in self._tiny_get_all_previous_workorders().sorted(lambda wo: wo._tiny_sort_key()):
            if previous.rework_return_id:
                return _('Công đoạn %s đang được chỉnh lại.', previous.name)
            if previous.review_mode == 'before' and previous.review_state != 'passed':
                return _('Công đoạn %s chưa được duyệt đạt.', previous.name)
        return False

    # ------------------------------------------------------------------
    # Hoàn thành / hủy
    # ------------------------------------------------------------------
    def button_finish(self):
        to_end = self.filtered(lambda wo: wo.state not in ('done', 'cancel'))
        res = super().button_finish()
        for workorder in to_end.filtered(lambda wo: wo.state == 'done'):
            if workorder.rework_return_id:
                workorder.rework_return_id._tiny_resolve()
            if workorder.review_mode in ('before', 'after') and not workorder.production_id.is_mrp_pattern:
                workorder._tiny_create_review()
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self._tiny_cancel_open_review_and_rework()
        return res

    def _tiny_cancel_open_review_and_rework(self):
        reviews = self.review_ids.filtered(lambda r: r.state in OPEN_REVIEW_STATES)
        if reviews:
            reviews._tiny_cancel()
        returns = self.env['mrp.workorder.return'].search([('workorder_id', 'in', self.ids), ('state', '=', 'open')])
        if returns:
            returns.write({'state': 'cancel'})
        self.filtered('rework_return_id').write({'rework_return_id': False})

    def _tiny_create_review(self):
        self.ensure_one()
        Review = self.env['mrp.workorder.review'].sudo()
        # Lượt duyệt cũ còn mở (trường hợp hiếm) thì hủy để chỉ còn một lượt chờ duyệt
        self.review_ids.filtered(lambda r: r.state in OPEN_REVIEW_STATES)._tiny_cancel()
        review = Review.create({
            'workorder_id': self.id,
            'round_no': max(self.review_ids.mapped('round_no') or [0]) + 1,
            'mode': self.review_mode,
        })
        for user in self.user_review_ids:
            review.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Duyệt công đoạn'),
                note=review.name,
                user_id=user.id,
            )
        return review

    # ------------------------------------------------------------------
    # Trả lại công đoạn
    # ------------------------------------------------------------------
    def action_open_return_wizard(self):
        self.ensure_one()
        self._tiny_check_reviewer()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Trả lại công đoạn'),
            'res_model': 'mrp.workorder.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_workorder_id': self.id,
                'default_review_id': self.env.context.get('default_review_id', False),
            },
        }

    def _tiny_reopen(self):
        """Mở lại công đoạn: done về 'ready', đang chạy thì đóng hết phiên giờ."""
        for workorder in self:
            if workorder.state == 'done':
                # state là compute store, set_state bỏ qua công đoạn done nên ghi trực tiếp
                workorder.write({'state': 'ready'})
            elif workorder.time_ids.filtered(lambda t: not t.date_end):
                workorder.end_all()

    def _tiny_create_return(self, target_wo, reasons, note=False, assign_users=None, review=False):
        """Trả công đoạn `self` (nơi phát hiện lỗi) về `target_wo` (chính nó hoặc công đoạn trước) để chỉnh lại."""
        self.ensure_one()
        Return = self.env['mrp.workorder.return'].sudo()
        production = self.production_id
        assign_users = assign_users or self.env['res.users']
        if production.state in ('done', 'cancel'):
            raise UserError(_('Lệnh sản xuất đã hoàn thành hoặc bị hủy, không trả lại công đoạn được.'))
        if not target_wo or target_wo.production_id != production:
            raise UserError(_('Công đoạn trả về phải thuộc cùng lệnh sản xuất.'))
        if target_wo.state == 'cancel':
            raise UserError(_('Công đoạn "%s" đã bị hủy.', target_wo.name))
        previous = self._tiny_get_all_previous_workorders()
        if target_wo != self and target_wo not in previous:
            raise UserError(_('Chỉ trả về được chính công đoạn này hoặc một công đoạn đứng trước.'))
        if target_wo.rework_return_id:
            raise UserError(_('Công đoạn "%s" đang có lượt chỉnh chưa xong.', target_wo.name))
        if self != target_wo and self.rework_return_id:
            raise UserError(_('Công đoạn "%s" đang có lượt chỉnh chưa xong.', self.name))

        reason_text = ', '.join(reasons.mapped('name')) or (note or '')
        ret = Return.create({
            'from_workorder_id': self.id,
            'workorder_id': target_wo.id,
            'review_id': review.id if review else False,
            'reason_ids': [(6, 0, reasons.ids)],
            'note': note,
            'user_id': self.env.user.id,
            'assign_user_ids': [(6, 0, assign_users.ids)],
            'previous_user_ids': [(6, 0, target_wo.user_mrp_ids.ids)],
            'user_replaced': bool(assign_users),
        })
        target_wo._tiny_reopen()
        target_vals = {'rework_return_id': ret.id}
        if assign_users:
            target_vals['user_mrp_ids'] = [(6, 0, assign_users.ids)]
        target_wo.write(target_vals)

        body = _('%(from)s bị trả về %(to)s: %(reason)s',
                 **{'from': self.name, 'to': target_wo.name, 'reason': reason_text})
        if self != target_wo:
            if self.state == 'done':
                # Công đoạn phát hiện lỗi đã xong: mở lại và tính giờ làm lại là giờ sửa
                own = Return.create({
                    'from_workorder_id': self.id,
                    'workorder_id': self.id,
                    'review_id': review.id if review else False,
                    'reason_ids': [(6, 0, reasons.ids)],
                    'note': _('Làm lại sau khi %s chỉnh xong', target_wo.name),
                    'user_id': self.env.user.id,
                })
                self._tiny_reopen()
                self.write({'rework_return_id': own.id})
            elif self.state not in ('cancel',):
                if self.time_ids.filtered(lambda t: not t.date_end):
                    self.end_all()
                    wait_reason = self.env.ref('tiny_approvals_mrp.mrp_reason_wait_previous_rework',
                                               raise_if_not_found=False)
                    if wait_reason:
                        self.env['mrp.pause.reason'].sudo().create({
                            'reason_id': wait_reason.id,
                            'user_id': self.env.user.id,
                            'workorder_id': self.id,
                        })
            key_from, key_to = self._tiny_sort_key(), target_wo._tiny_sort_key()
            middle = previous.filtered(
                lambda wo: wo != target_wo and wo.state == 'done' and key_to < wo._tiny_sort_key() < key_from)
            if middle:
                body = Markup('%s<br/>%s') % (
                    body, _('Các công đoạn ở giữa giữ nguyên: %s', ', '.join(middle.mapped('name'))))
        production.message_post(body=body)
        return ret
