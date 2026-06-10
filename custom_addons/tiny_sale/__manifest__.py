# -*- coding: utf-8 -*-

{
    'name': "Tiny: Sale",
    'summary': "Tiny: Sale",
    'description': "Tiny: Sale",
    'author': "Tiny",
    'website': "https://tiny.com.vn/",
    'category': 'Sale',
    'version': '19.0.0.1',
    'license': 'LGPL-3',
    'depends': [
        'base', 'sale', 'sale_order_line_product_image'
    ],
    'data': [
        # 'data/sequence.xml',
        'views/sale_views.xml',
        'views/account_move_views.xml',
        'report/ir_actions_report.xml',
        'report/ir_actions_report_templates.xml',

    ],
    'application': True,
    'installable': True,
}
