# -*- coding: utf-8 -*-

{
    'name': "Tiny: Sale Purchase Stock",
    'summary': "Tiny: Sale Purchase Stock",
    'description': "Tiny: Sale Purchase Stock",
    'author': "Tiny",
    'website': "https://tiny.com.vn/",
    'category': 'Sale',
    'version': '19.0.0.1',
    'license': 'LGPL-3',
    'depends': [
        'base', 'tiny_sale_purchase',  'sale_stock'
    ],
    'data': [
        'views/stock_route_views.xml',
    ],
    'application': True,
    'installable': True,
}
