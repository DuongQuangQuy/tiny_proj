from odoo import fields, models


class SaleTrial(models.Model):
    _name = 'sale.trial'
    _description = 'Thử hàng'
    _order = 'name'

    name = fields.Char(string='Tên', required=True, translate=True)
    workcenter_id = fields.Many2one('mrp.workcenter', string='Công đoạn')
