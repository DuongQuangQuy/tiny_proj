# -*- coding: utf-8 -*-

{
    'name': "Tiny: Sale MRP",
    'summary': "Dự toán giá bằng BOM cho sản phẩm đặt theo yêu cầu khách hàng",
    'description': """
Công ty thương mại lập phiếu dự toán (BOM sơ bộ + chi phí) cho sản phẩm làm theo
yêu cầu khách hàng khi sản phẩm chưa tồn tại. Khi khách đồng ý, phiếu dự toán tạo
sản phẩm mới, BOM ở công ty sản xuất và đơn bán hàng. Luồng liên công ty có sẵn
(SO -> PO -> SO công ty sản xuất -> MO) dùng lại BOM này để sản xuất.
    """,
    'author': "Tiny",
    'website': "https://tiny.com.vn/",
    'category': 'Sale',
    'version': '19.0.0.1',
    'license': 'LGPL-3',
    'depends': [
        'base', 'sale_mrp', 'mrp_workorder', 'tiny_contacts', 'tiny_product', 'tiny_sale_purchase_stock',
    ],
    'data': [
        'data/sequence.xml',
        'security/security.xml',
        'security/ir.model.access.csv',

        'views/sale_estimate_views.xml',
        'views/sale_order_views.xml',
        'views/res_company_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
}
