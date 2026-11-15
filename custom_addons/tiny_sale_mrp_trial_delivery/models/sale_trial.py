from odoo import fields, models


class SaleTrial(models.Model):
    _name = 'sale.trial'
    _description = 'Fitting'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    workcenter_id = fields.Many2one('mrp.workcenter', string='Work Order')
