# -*- coding: utf-8 -*-
# Part of Browseinfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models,_
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    image_128 = fields.Binary(string="Hình ảnh")

    @api.onchange('product_id')
    def onchange_sale_product_image(self):
        for line in self:
            if line.product_id.image_128:
                line.image_128 = line.product_id.image_128
            else:
                line.image_128 = False


