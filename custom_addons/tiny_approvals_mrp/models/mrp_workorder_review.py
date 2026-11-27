from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpWorkorderReview(models.Model):
    _name = 'mrp.workorder.review'
    _description = 'Work Order Review Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    workorder_id = fields.Many2one('mrp.workorder', string='Work Order', required=True, ondelete='cascade', index=True)
    production_id = fields.Many2one('mrp.production', string='Manufacturing Order', related='workorder_id.production_id',
                                    store=True, index=True)
    workcenter_id = fields.Many2one('mrp.workcenter', string='Work Center', related='workorder_id.workcenter_id',
                                    store=True)
    product_id = fields.Many2one('product.product', string='Product', related='production_id.product_id')
    company_id = fields.Many2one('res.company', related='workorder_id.company_id', store=True)
    round_no = fields.Integer(string='Round', default=1)
    mode = fields.Selection([('before', 'Review Before'), ('after', 'Review After')], string='Review Mode',
                            default='before', required=True)
    state = fields.Selection([
        ('waiting', 'Waiting for Manager Review'),
        ('reviewing', 'Under Review'),
        ('paused', 'Pause Review'),
        ('passed', 'Pass'),
        ('failed', 'Fail'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='waiting', required=True, tracking=True, index=True)
    reviewer_id = fields.Many2one('res.users', string='Taken By', tracking=True)
    user_review_ids = fields.Many2many('res.users', string='Review Managers', related='workorder_id.user_review_ids')
    worker_ids = fields.Many2many('res.users', string='Workers', related='workorder_id.user_mrp_ids')
    date_request = fields.Datetime(string='Request Date', default=fields.Datetime.now, readonly=True)
    date_start = fields.Datetime(string='Review Start', readonly=True)
    date_done = fields.Datetime(string='Review End', readonly=True)
    date_last_start = fields.Datetime(string='Running Review Session Start', readonly=True)
    review_duration = fields.Float(string='Review Duration (minutes)', readonly=True)

    # Khi chưa đạt
    defect_reason_ids = fields.Many2many('mrp.reason', 'mrp_workorder_review_reason_rel', 'review_id', 'reason_id',
                                         string='Defects', domain=[('reason_type', '=', 'defect')])
    note = fields.Text(string='Notes')
    return_workorder_id = fields.Many2one('mrp.workorder', string='Work Order to Rework',
                                          compute='_compute_return_workorder_id', store=True, readonly=False,
                                          domain="[('production_id', '=', production_id), ('state', '!=', 'cancel')]")
    assign_user_ids = fields.Many2many('res.users', 'mrp_workorder_review_assign_user_rel', 'review_id', 'user_id',
                                       string='Rework Responsible', compute='_compute_assign_user_ids',
                                       store=True, readonly=False)
    return_id = fields.Many2one('mrp.workorder.return', string='Rework Round', readonly=True)

    @api.depends('production_id.name', 'workorder_id.name', 'round_no')
    def _compute_name(self):
        for review in self:
            review.name = _('%(mo)s - %(wo)s - Round %(n)s', mo=review.production_id.name or '',
                            wo=review.workorder_id.name or '', n=review.round_no)

    @api.depends('workorder_id')
    def _compute_return_workorder_id(self):
        """Mặc định trả về chính công đoạn đang duyệt, người duyệt đổi tay nếu cần."""
        for review in self:
            if not review.return_workorder_id:
                review.return_workorder_id = review.workorder_id

    @api.depends('return_workorder_id')
    def _compute_assign_user_ids(self):
        """Mặc định người phụ trách chỉnh là nhân viên thực hiện của công đoạn trả về, sửa tay được."""
        for review in self:
            review.assign_user_ids = review.return_workorder_id.user_mrp_ids

    # ------------------------------------------------------------------
    def _tiny_check_reviewer(self):
        for review in self:
            review.workorder_id._tiny_check_reviewer()

    def _tiny_close_session(self):
        now = fields.Datetime.now()
        for review in self:
            if review.date_last_start:
                review.review_duration += (now - review.date_last_start).total_seconds() / 60.0
            review.date_last_start = False

    def _tiny_done_activities(self):
        activities = self.sudo().activity_ids
        if activities:
            activities.unlink()

    def action_start_review(self):
        self._tiny_check_reviewer()
        now = fields.Datetime.now()
        for review in self:
            if review.state not in ('waiting', 'paused'):
                raise UserError(_('Only pending or paused requests can be taken for review or resumed.'))
            vals = {'state': 'reviewing', 'date_last_start': now}
            if not review.reviewer_id:
                vals['reviewer_id'] = self.env.user.id
            if not review.date_start:
                vals['date_start'] = now
            review.write(vals)
        return True

    def action_pause_review(self):
        self._tiny_check_reviewer()
        for review in self:
            if review.state != 'reviewing':
                raise UserError(_('Only requests under review can be paused.'))
        self._tiny_close_session()
        self.write({'state': 'paused'})
        return True

    def action_pass(self):
        self._tiny_check_reviewer()
        for review in self:
            if review.state != 'reviewing':
                raise UserError(_('Click Take Review before marking Pass / Fail.'))
        self._tiny_close_session()
        self.write({'state': 'passed', 'date_done': fields.Datetime.now()})
        self._tiny_done_activities()
        for review in self:
            review.production_id.message_post(body=_('Work order %(wo)s (round %(n)s) was passed by %(user)s.',
                                                     wo=review.workorder_id.name, n=review.round_no,
                                                     user=self.env.user.name))
        return True

    def action_fail(self, defect_reason_ids=None, note=None, return_workorder_id=None, assign_user_ids=None):
        """Chưa đạt: mở lượt chỉnh trên công đoạn phải chỉnh (mặc định chính công đoạn này)."""
        self.ensure_one()
        self._tiny_check_reviewer()
        if self.state != 'reviewing':
            raise UserError(_('Click Take Review before marking Pass / Fail.'))
        Workorder = self.env['mrp.workorder']
        Reason = self.env['mrp.reason']
        Users = self.env['res.users']
        vals = {}
        if defect_reason_ids is not None:
            vals['defect_reason_ids'] = [(6, 0, Reason.browse(defect_reason_ids).ids if not isinstance(
                defect_reason_ids, models.BaseModel) else defect_reason_ids.ids)]
        if note is not None:
            vals['note'] = note
        if return_workorder_id is not None:
            vals['return_workorder_id'] = return_workorder_id.id if isinstance(
                return_workorder_id, models.BaseModel) else return_workorder_id
        if assign_user_ids is not None:
            vals['assign_user_ids'] = [(6, 0, Users.browse(assign_user_ids).ids if not isinstance(
                assign_user_ids, models.BaseModel) else assign_user_ids.ids)]
        if vals:
            self.write(vals)
        if not self.defect_reason_ids and not self.note:
            raise UserError(_('Please select a defect or enter a note when marking Fail.'))
        target = self.return_workorder_id or self.workorder_id
        assign_users = self.assign_user_ids or target.user_mrp_ids
        self._tiny_close_session()
        self.write({
            'state': 'failed',
            'date_done': fields.Datetime.now(),
            'return_workorder_id': target.id,
            'assign_user_ids': [(6, 0, assign_users.ids)],
        })
        self._tiny_done_activities()
        ret = self.workorder_id._tiny_create_return(target, self.defect_reason_ids, self.note,
                                                    assign_users, review=self)
        self.return_id = ret
        return True

    def _tiny_cancel(self):
        self._tiny_close_session()
        self.write({'state': 'cancel'})
        self._tiny_done_activities()

    def action_open_return_wizard(self):
        self.ensure_one()
        return self.workorder_id.with_context(default_review_id=self.id).action_open_return_wizard()


class MrpWorkorderReturn(models.Model):
    _name = 'mrp.workorder.return'
    _description = 'Work Order Return / Rework'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    from_workorder_id = fields.Many2one('mrp.workorder', string='From Work Order', required=True, ondelete='cascade',
                                        index=True)
    workorder_id = fields.Many2one('mrp.workorder', string='Work Order to Rework', required=True, ondelete='cascade',
                                   index=True)
    production_id = fields.Many2one('mrp.production', string='Manufacturing Order', related='workorder_id.production_id',
                                    store=True, index=True)
    workcenter_id = fields.Many2one('mrp.workcenter', string='Work Center', related='workorder_id.workcenter_id',
                                    store=True)
    company_id = fields.Many2one('res.company', related='workorder_id.company_id', store=True)
    review_id = fields.Many2one('mrp.workorder.review', string='Review Round', ondelete='set null')
    reason_ids = fields.Many2many('mrp.reason', 'mrp_workorder_return_reason_rel', 'return_id', 'reason_id',
                                  string='Reasons', domain=[('reason_type', 'in', ('defect', 'return'))])
    note = fields.Text(string='Notes')
    user_id = fields.Many2one('res.users', string='Returned By', default=lambda self: self.env.user)
    assign_user_ids = fields.Many2many('res.users', 'mrp_workorder_return_assign_user_rel', 'return_id', 'user_id',
                                       string='Rework Responsible')
    previous_user_ids = fields.Many2many('res.users', 'mrp_workorder_return_prev_user_rel', 'return_id', 'user_id',
                                         string='Operators Before Return')
    user_replaced = fields.Boolean(string='Operators Changed')
    date = fields.Datetime(string='Return Date', default=fields.Datetime.now, readonly=True)
    date_resolved = fields.Datetime(string='Rework Done Date', readonly=True)
    state = fields.Selection([
        ('open', 'Reworking'),
        ('done', 'Rework Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='open', required=True, tracking=True, index=True)
    time_ids = fields.One2many('mrp.workcenter.productivity', 'return_id', string='Rework Time Sessions')
    rework_duration = fields.Float(string='Rework Time (minutes)', compute='_compute_rework_duration', store=True)
    round_no = fields.Integer(string='Rework Round', compute='_compute_round_no')

    @api.depends('workorder_id.name', 'from_workorder_id.name', 'production_id.name')
    def _compute_name(self):
        for record in self:
            record.name = _('%(mo)s - %(from)s → %(to)s', **{
                'mo': record.production_id.name or '', 'from': record.from_workorder_id.name or '',
                'to': record.workorder_id.name or ''})

    @api.depends('time_ids.duration')
    def _compute_rework_duration(self):
        for record in self:
            record.rework_duration = sum(record.time_ids.mapped('duration'))

    def _compute_round_no(self):
        for record in self:
            returns = record.workorder_id.return_ids.filtered(lambda r: r.state != 'cancel').sorted('id')
            record.round_no = (returns.ids.index(record.id) + 1) if record.id in returns.ids else 0

    def _tiny_resolve(self):
        """Công đoạn chỉnh xong: đóng lượt chỉnh, trả lại người thực hiện cũ."""
        for record in self.filtered(lambda r: r.state == 'open'):
            record.write({'state': 'done', 'date_resolved': fields.Datetime.now()})
            workorder = record.workorder_id
            vals = {}
            if workorder.rework_return_id == record:
                vals['rework_return_id'] = False
            if record.user_replaced:
                vals['user_mrp_ids'] = [(6, 0, record.previous_user_ids.ids)]
            if vals:
                workorder.write(vals)
