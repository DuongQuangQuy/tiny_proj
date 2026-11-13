from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpWorkorderReturnWizard(models.TransientModel):
    _name = 'mrp.workorder.return.wizard'
    _description = 'Trả lại công đoạn'

    workorder_id = fields.Many2one('mrp.workorder', string='Công đoạn phát hiện lỗi', required=True, readonly=True)
    production_id = fields.Many2one('mrp.production', related='workorder_id.production_id')
    review_id = fields.Many2one('mrp.workorder.review', string='Lượt duyệt', readonly=True)
    allowed_workorder_ids = fields.Many2many('mrp.workorder', compute='_compute_allowed_workorder_ids')
    target_workorder_id = fields.Many2one('mrp.workorder', string='Trả về công đoạn', required=True,
                                          domain="[('id', 'in', allowed_workorder_ids)]")
    reason_ids = fields.Many2many('mrp.reason', string='Lý do', domain=[('reason_type', 'in', ('defect', 'return'))])
    note = fields.Text(string='Ghi chú')
    assign_user_ids = fields.Many2many('res.users', string='Người phụ trách chỉnh')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        workorder = self.env['mrp.workorder'].browse(res.get('workorder_id') or self.env.context.get('active_id'))
        if workorder and 'target_workorder_id' in fields_list and not res.get('target_workorder_id'):
            res['target_workorder_id'] = workorder.id
            res['assign_user_ids'] = [(6, 0, workorder.user_mrp_ids.ids)]
        return res

    @api.depends('workorder_id')
    def _compute_allowed_workorder_ids(self):
        for wizard in self:
            wo = wizard.workorder_id
            wizard.allowed_workorder_ids = (wo | wo._tiny_get_all_previous_workorders()) if wo else False

    @api.onchange('target_workorder_id')
    def _onchange_target_workorder_id(self):
        if self.target_workorder_id:
            self.assign_user_ids = self.target_workorder_id.user_mrp_ids

    def action_confirm(self):
        self.ensure_one()
        self.workorder_id._tiny_check_reviewer()
        if not self.reason_ids and not self.note:
            raise UserError(_('Vui lòng chọn lý do hoặc ghi chú.'))
        self.workorder_id._tiny_create_return(self.target_workorder_id, self.reason_ids, self.note,
                                              self.assign_user_ids, review=self.review_id)
        return {'type': 'ir.actions.act_window_close'}
