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
    estimate_markup_factor = fields.Float(
        string='Hệ số giá bán mặc định', default=1,
        help="Giá bán dự toán = Giá vốn dự toán x hệ số này.")
