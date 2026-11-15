from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    estimate_route_ids = fields.Many2many(
        'stock.route', 'res_company_estimate_route_rel', 'company_id', 'route_id',
        string='Routes for Estimated Products',
        help='Assigned to products created from estimates. MTO + Buy are required so the sales order creates a PO to the manufacturing company.')
    estimate_categ_id = fields.Many2one(
        'product.category', string='Estimated Product Category',
        help='Default category on estimate lines.')

    # Tham số tính giá (theo sheet bespoke của file báo giá), mặc định cho dòng dự toán mới
    estimate_studio_rate = fields.Float(
        string='Studio Rate', default=1.0, help='Studio cost = Cost x this rate.')
    estimate_profit_rate_lv1 = fields.Float(string='Profit LV1', default=0.20)
    estimate_profit_rate_lv2 = fields.Float(string='Profit LV2', default=0.25)
    estimate_markup_lv1_1 = fields.Float(string='LV1 Factor (1)', default=1.8)
    estimate_markup_lv1_2 = fields.Float(string='LV1 Factor (2)', default=2.2)
    estimate_markup_lv1_3 = fields.Float(string='LV1 Factor (3)', default=2.5)
    estimate_markup_lv2_1 = fields.Float(string='LV2 Factor (1)', default=1.9)
    estimate_markup_lv2_2 = fields.Float(string='LV2 Factor (2)', default=2.2)
    estimate_markup_lv2_3 = fields.Float(string='LV2 Factor (3)', default=2.5)
    estimate_price_rounding = fields.Monetary(
        string='Final Price Rounding', default=100000, help='The final price is rounded to a multiple of this amount.')
    estimate_packaging_garment_bag = fields.Monetary(string='Garment bag', default=42000)
    estimate_packaging_price_tag = fields.Monetary(string='Price tag', default=5500)
    estimate_packaging_box = fields.Monetary(string='Paper Bag / Box', default=40000)
    estimate_showroom_factor_1 = fields.Float(
        string='Mark up 1 Factor', default=0.7, help='Mark up 1 = Final price x this factor.')
    estimate_showroom_factor_2 = fields.Float(
        string='Mark up 2 Factor', default=2.5, help='Mark up 2 = Mark up 1 x this factor.')
    estimate_showroom_factor_3 = fields.Float(
        string='Mark up 2 (LV2) Factor', default=2.8, help='Mark up 2 (LV2) = Total cost LV2 x this factor.')
    estimate_wsp_rate = fields.Float(string='Wholesale Rate', default=0.40)
    estimate_ecom_rate = fields.Float(string='E-commerce Rate', default=0.50)
    estimate_wsp2_rate = fields.Float(string='Wholesale Rate 2', default=0.42)
    estimate_usd_currency_id = fields.Many2one(
        'res.currency', string='USD Conversion Currency',
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
        help='Prices are converted with the Odoo exchange rates. If the currency is inactive or has no rate, the converted price is 0.')
