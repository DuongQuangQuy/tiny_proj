# -*- coding: utf-8 -*-

{
    'name': "Tiny: Sale Advance Wallet",
    'summary': "Tiny: Sale Advance Wallet",
    'description': "Tiny: Sale Advance Wallet",
    'author': "Tiny",
    'website': "https://tiny.com.vn/",
    'category': 'Sale/Wallet',
    'version': '19.0.0.1',
    'license': 'LGPL-3',
    'depends': [
        'base', 'sale_advance_payment',  'to_wallet'
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/sale_advance_payment_wzd_view.xml',
        'views/sale_advance_line_views.xml',
    ],
    'application': True,
    'installable': True,
}
