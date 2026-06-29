# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MrpPauseReason(models.Model):
    _name = 'mrp.pause.reason'
    _description = 'MRP Pause Reason'
    _rec_name = 'name'

    name = fields.Char(string='Lý do tạm dừng', related='reason_id.name', store=True)
    user_id = fields.Many2one('res.users', string='Người yêu cầu')
    workorder_id = fields.Many2one('mrp.workorder', string='Công đoạn')
    date = fields.Datetime(string='Ngày yêu cầu', default=fields.Datetime.now, readonly=True)
    reason_id = fields.Many2one('mrp.reason', string='Lý do')
    