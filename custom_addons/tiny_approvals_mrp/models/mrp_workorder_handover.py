from odoo import api, fields, models, _


class MrpWorkorderHandover(models.Model):
    """Bàn giao: công đoạn trước (chưa xong) cho phép một công đoạn sau bắt đầu làm song song."""
    _name = 'mrp.workorder.handover'
    _description = 'Work Order Handover'
    _order = 'id desc'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    from_workorder_id = fields.Many2one('mrp.workorder', string='Handed Over From', required=True,
                                        ondelete='cascade', index=True)
    workorder_id = fields.Many2one('mrp.workorder', string='Handed Over To', required=True,
                                   ondelete='cascade', index=True)
    production_id = fields.Many2one('mrp.production', string='Manufacturing Order',
                                    related='workorder_id.production_id', store=True, index=True)
    company_id = fields.Many2one('res.company', related='workorder_id.company_id', store=True)
    from_state = fields.Selection(string='Source Status When Handed Over', selection=[
        ('blocked', 'Blocked'),
        ('ready', 'To Do'),
        ('progress', 'In Progress'),
    ], readonly=True)
    user_id = fields.Many2one('res.users', string='Handed Over By', default=lambda self: self.env.user, readonly=True)
    date = fields.Datetime(string='Handover Date', default=fields.Datetime.now, readonly=True)
    note = fields.Text(string='Notes')

    _from_to_uniq = models.Constraint('UNIQUE(from_workorder_id, workorder_id)',
                                      'This work order has already been handed over to that work order.')

    @api.depends('production_id.name', 'from_workorder_id.name', 'workorder_id.name')
    def _compute_name(self):
        for record in self:
            record.name = _('%(mo)s - %(from)s → %(to)s', mo=record.production_id.name or '',
                            **{'from': record.from_workorder_id.name or '', 'to': record.workorder_id.name or ''})
