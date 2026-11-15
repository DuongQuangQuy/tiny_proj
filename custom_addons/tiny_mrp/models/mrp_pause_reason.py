# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MrpPauseReason(models.Model):
    _name = 'mrp.pause.reason'
    _description = 'MRP Pause Reason'
    _rec_name = 'name'

    name = fields.Char(string='Pause Reason', related='reason_id.name', store=True)
    user_id = fields.Many2one('res.users', string='Requested By')
    workorder_id = fields.Many2one('mrp.workorder', string='Work Order')
    date = fields.Datetime(string='Request Date', default=fields.Datetime.now, readonly=True)
    reason_id = fields.Many2one('mrp.reason', string='Reason')
    