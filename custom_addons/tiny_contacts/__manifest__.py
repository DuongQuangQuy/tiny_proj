# -*- coding: utf-8 -*-

{
    'name': "Tiny: Contacts",
    'summary': "Tiny: Contacts",
    'description': "Tiny: Contacts",
    'author': "Tiny",
    'website': "https://tiny.com.vn/",
    'category': 'Contacts',
    'version': '19.0.0.1',
    'license': 'LGPL-3',
    'depends': [
        'base', 'contacts',
    ],
    'data': [
        'data/sequence.xml',
        'views/res_partner_views.xml',
        'views/res_company_views.xml',
        # 'report/ir_actions_report_templates.xml',

    ],
    'application': True,
    'installable': True,
}
