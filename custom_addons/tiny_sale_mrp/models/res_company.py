from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    estimate_route_ids = fields.Many2many(
        'stock.route', 'res_company_estimate_route_rel', 'company_id', 'route_id',
        string='Tuyến cho sản phẩm dự toán',
        help="Gán cho sản phẩm tạo từ phiếu dự toán. Cần có MTO + Mua để đơn hàng "
             "sinh PO sang công ty sản xuất.")
    estimate_categ_id = fields.Many2one(
        'product.category', string='Danh mục sản phẩm dự toán',
        help="Danh mục mặc định trên dòng dự toán.")

    # Tham số tính giá (theo sheet bespoke của file báo giá), mặc định cho dòng dự toán mới
    estimate_studio_rate = fields.Float(
        string='Tỷ lệ studio', default=1.0, help="Studio cost = Giá vốn x tỷ lệ này.")
    estimate_profit_rate_lv1 = fields.Float(string='Lợi nhuận LV1', default=0.20)
    estimate_profit_rate_lv2 = fields.Float(string='Lợi nhuận LV2', default=0.25)
    estimate_markup_lv1_1 = fields.Float(string='Hệ số LV1 (1)', default=1.8)
    estimate_markup_lv1_2 = fields.Float(string='Hệ số LV1 (2)', default=2.2)
    estimate_markup_lv1_3 = fields.Float(string='Hệ số LV1 (3)', default=2.5)
    estimate_markup_lv2_1 = fields.Float(string='Hệ số LV2 (1)', default=1.9)
    estimate_markup_lv2_2 = fields.Float(string='Hệ số LV2 (2)', default=2.2)
    estimate_markup_lv2_3 = fields.Float(string='Hệ số LV2 (3)', default=2.5)
    estimate_price_rounding = fields.Monetary(
        string='Làm tròn giá chốt', default=100000, help="Giá chốt làm tròn đến bội số của số này.")
    estimate_packaging_garment_bag = fields.Monetary(string='Garment bag', default=42000)
    estimate_packaging_price_tag = fields.Monetary(string='Price tag', default=5500)
    estimate_packaging_box = fields.Monetary(string='Túi giấy / hộp', default=40000)
    estimate_showroom_factor_1 = fields.Float(
        string='Hệ số mark up 1', default=0.7, help="Mark up 1 = Giá chốt x hệ số này.")
    estimate_showroom_factor_2 = fields.Float(
        string='Hệ số mark up 2', default=2.5, help="Mark up 2 = Mark up 1 x hệ số này.")
    estimate_showroom_factor_3 = fields.Float(
        string='Hệ số mark up 2 (LV2)', default=2.8, help="Mark up 2 (LV2) = Total cost LV2 x hệ số này.")
    estimate_wsp_rate = fields.Float(string='Tỷ lệ giá sỉ', default=0.40)
    estimate_ecom_rate = fields.Float(string='Tỷ lệ ecommerce', default=0.50)
    estimate_wsp2_rate = fields.Float(string='Tỷ lệ giá sỉ 2', default=0.42)
    estimate_usd_currency_id = fields.Many2one(
        'res.currency', string='Tiền tệ quy đổi USD',
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
        help="Quy đổi giá theo tỷ giá Odoo. Tiền tệ chưa bật hoặc chưa có tỷ giá thì giá quy đổi = 0.")
