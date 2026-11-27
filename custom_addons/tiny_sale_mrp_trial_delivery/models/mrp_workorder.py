# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    # Công đoạn khách thử hàng: khu vực sản xuất trùng khu vực của Fitting trên đơn bán gốc
    is_fitting = fields.Boolean(string='Fitting Operation', compute='_compute_is_fitting')

    @api.depends('workcenter_id', 'production_id')
    def _compute_is_fitting(self):
        for workorder in self:
            production = workorder.production_id
            workorder.is_fitting = bool(production) and production._is_fitting_workcenter(workorder.workcenter_id)
