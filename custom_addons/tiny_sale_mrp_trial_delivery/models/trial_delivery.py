# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta


class TrialDelivery(models.Model):
    _name = 'trial.delivery'
    _description = 'Trial Delivery'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Trial Delivery Count',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('delivered', 'Trial Delivered'),
        ('returned', 'Returned by Customer'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    # Liên kết đơn bán hàng
    # sale_order_id = fields.Many2one(
    #     'sale.order',
    #     string='Đơn bán hàng',
    #     tracking=True,
    #     domain=[('state', 'in', ['sale', 'done'])],
    # )
    # sale_partner_id = fields.Many2one(
    #     'res.partner',
    #     string='Khách hàng',
    #     related='sale_order_id.partner_id',
    #     store=True,
    # )

    # Liên kết lệnh sản xuất
    production_id = fields.Many2one(
        'mrp.production',
        string='Manufacturing Order',
        tracking=True,
        domain=[('state', 'in', ['confirmed', 'progress', 'to_close', 'done'])],
    )
    sale_origin = fields.Char(
        string='Source Order',
       
    )

    # Thông tin khách hàng (có thể khác với đơn hàng)
    partner_id = fields.Many2one(
        'res.partner',
        string='Delivered To',
        required=True,
        tracking=True,
    )
    partner_shipping_id = fields.Many2one(
        'res.partner',
        string='Delivery Address',
        tracking=True,
    )
    partner_phone = fields.Char(
        string='Phone',
        related='partner_id.phone',
    )
    note = fields.Text(string='Internal Notes')
    customer_note = fields.Text(string='Customer Notes')
    date_delivery = fields.Datetime(
        string='Trial Delivery Date', default=fields.Datetime.now, required=True)
    date_return = fields.Datetime(
        string='Customer Return Date', required=True, default=lambda self: self._default_date_return())
    line_ids = fields.One2many(
        'trial.delivery.line',
        'trial_delivery_id',
        string='Trial Delivery Lines'
    )

    def _default_date_return(self):
        return fields.Datetime.now() + timedelta(days=7)

    @api.model_create_multi
    def create(self, vals):
        for val in vals:
            if val.get('name', _('New')) == _('New'):
                val['name'] = self.env['ir.sequence'].next_by_code('trial.delivery') or _('New')
        return super(TrialDelivery, self).create(vals)

    def action_delivered(self):
        for rec in self:
            rec.state = 'delivered'

    def action_returned(self):
        for rec in self:
            rec.state = 'returned'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancel'


class TrialDeliveryLine(models.Model):
    _name = 'trial.delivery.line'
    _description = 'Trial Delivery Line'

    trial_delivery_id = fields.Many2one(
        'trial.delivery',
        string='Trial Delivery',
        required=True,
        ondelete='cascade',
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        domain=[('type', 'in', ['product', 'consu'])],
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        related='product_id.product_tmpl_id',
        string='Product Template',
    )
    description = fields.Text(
        string='Description',
        compute='_compute_description',
        store=True,
    )

    qty_trial = fields.Float(
        string='Trial Quantity',
        required=True,
        default=1.0,
        digits='Product Unit of Measure',
    )

    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        related='product_id.uom_id',
    )

    @api.depends('product_id')
    def _compute_description(self):
        for line in self:
            if line.product_id:
                line.description = line.product_id.description_sale or line.product_id.name
            else:
                line.description = ''