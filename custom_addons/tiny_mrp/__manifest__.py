# -*- coding: utf-8 -*-

{
    'name': "Tiny: Mrp",
    'summary': "Tiny: Mrp",
    'description': "Tiny: Mrp",
    'author': "Tiny",
    'website': "https://tiny.com.vn/",
    'category': 'Mrp',
    'version': '19.0.0.1',
    'license': 'LGPL-3',
    'depends': [
        'base', 'mrp', 'portal', 'website'
    ],
    'data': [
        'views/res_users_views.xml',
        'views/mrp_workcenter_views.xml',
        'views/mrp_workorder_views.xml',
        'views/menus.xml',
        'views/mrp_workorder_portal_template.xml',
        # 'views/mrp_production_views.xml',

    ],
    'assets': {
        'web.assets_frontend': [
            'tiny_mrp/static/src/css/portal_css.scss',
        ],
    },
    'application': True,
    'installable': True,
}
