# -*- coding: utf-8 -*-

{
    'name': "Tiny: Sale Purchase",
    'summary': "Tiny: Sale Purchase",
    'description': "Tiny: Sale Purchase",
    'author': "Tiny",
    'website': "https://tiny.com.vn/",
    'category': 'Sale',
    'version': '19.0.0.1',
    'license': 'LGPL-3',
    'depends': [
        'base', 'sale_purchase',  'tiny_sale'
    ],
    'data': [
        'views/sale_views.xml',
        'views/purchase_views.xml',
    ],
    'application': True,
    'installable': True,
}
