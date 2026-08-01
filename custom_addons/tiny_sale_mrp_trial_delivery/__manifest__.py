# -*- coding: utf-8 -*-

{
    'name': "Tiny: Sale MRP Trial Delivery",
    'summary': "Tiny: Sale MRP Trial Delivery",
    'description': "Tiny: Sale MRP Trial Delivery",
    'author': "Tiny",
    'website': "https://tiny.com.vn/",
    'category': 'Sale',
    'version': '19.0.0.1',
    'license': 'LGPL-3',
    'depends': [
        'base', 'sale_mrp','tiny_sale_purchase',
    ],
    'data': [
        'data/sequence.xml',
        'security/ir.model.access.csv',

        # 'views/sale_views.xml',
        'views/trial_delivery_views.xml',
        'views/mrp_production_views.xml',
        'views/menus.xml',

    ],
    'application': True,
    'installable': True,
}
