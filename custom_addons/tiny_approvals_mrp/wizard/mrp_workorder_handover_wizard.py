from odoo import api, fields, models


class MrpWorkorderHandoverWizard(models.TransientModel):
    _name = 'mrp.workorder.handover.wizard'
    _description = 'Hand Over Work Order'

    workorder_id = fields.Many2one('mrp.workorder', string='Hand Over From', required=True, readonly=True)
    production_id = fields.Many2one('mrp.production', related='workorder_id.production_id')
    allowed_workorder_ids = fields.Many2many('mrp.workorder', compute='_compute_allowed_workorder_ids')
    target_workorder_ids = fields.Many2many('mrp.workorder', string='Hand Over To', required=True,
                                            domain="[('id', 'in', allowed_workorder_ids)]")
    note = fields.Text(string='Notes')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        workorder = self.env['mrp.workorder'].browse(res.get('workorder_id') or self.env.context.get('active_id'))
        if workorder and 'target_workorder_ids' in fields_list and not res.get('target_workorder_ids'):
            # Mặc định chọn công đoạn kế tiếp
            targets = workorder._tiny_get_handover_targets()
            if targets:
                res['target_workorder_ids'] = [(6, 0, targets[:1].ids)]
        return res

    @api.depends('workorder_id')
    def _compute_allowed_workorder_ids(self):
        for wizard in self:
            wo = wizard.workorder_id
            wizard.allowed_workorder_ids = wo._tiny_get_handover_targets() if wo else False

    def action_confirm(self):
        self.ensure_one()
        self.workorder_id._tiny_handover(self.target_workorder_ids, self.note)
        return {'type': 'ir.actions.act_window_close'}
