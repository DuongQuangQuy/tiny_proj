# -*- coding: utf-8 -*-

{
    'name': "Tiny: Sale MRP Trial Delivery",
    'summary': "Tiny: Sale MRP Trial Delivery",
    'description': "Tiny: Sale MRP Trial Delivery",
    'author': "Tiny",
    'website': "https://tiny.com.vn/",
    'category': 'Sale',
    'version': '19.0.0.2',
    'license': 'LGPL-3',
    'depends': [
        'base', 'sale_mrp', 'tiny_sale_purchase', 'tiny_mrp', 'tiny_sale_mrp',
    ],
    'data': [
        'data/sequence.xml',
        'security/ir.model.access.csv',

        'views/sale_trial_views.xml',
        'views/sale_views.xml',
        'report/sale_order_report_templates.xml',
        'views/trial_delivery_views.xml',
        'views/mrp_production_views.xml',
        'views/mrp_production_portal_template.xml',
        'report/mrp_production_report.xml',
        'views/menus.xml',

    ],
    'application': True,
    'installable': True,
}
