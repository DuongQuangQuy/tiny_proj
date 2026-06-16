# -*- coding: utf-8 -*-

{
    'name': "Tiny: Wallet Loyalty",
    'summary': "Tiny: Wallet Loyalty",
    'description': "Tiny: Wallet Loyalty",
    'author': "Tiny",
    'website': "https://tiny.com.vn/",
    'category': 'Wallet',
    'version': '19.0.0.1',
    'license': 'LGPL-3',
    'depends': [
        'to_wallet',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/wallet_loyalty_rule_views.xml',
        'views/account_payment_views.xml',
        'views/wallet_payment_creation_wizard_views.xml',
    ],
    'application': True,
    'installable': True,
}
