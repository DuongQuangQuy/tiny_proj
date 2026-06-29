# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MrpReason(models.Model):
    _name = 'mrp.reason'
    _description = 'MRP Reason'
    _rec_name = 'name'

    name = fields.Char(string='Tên', required=True)
    
    