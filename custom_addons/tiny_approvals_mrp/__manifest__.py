# -*- coding: utf-8 -*-

{
    'name': "Tiny: Approvals Mrp",
    'summary': "Tiny: Approvals Mrp",
    'description': "Tiny: Approvals Mrp",
    'author': "Tiny",
    'website': "https://tiny.com.vn/",
    'category': 'Approvals/Mrp',
    'version': '19.0.0.1',
    'license': 'LGPL-3',
    'depends': [
        'base', 'tiny_mrp', 'approvals', 'tiny_contacts'
    ],
    'data': [
        # 'security/ir.model.access.csv',
        # 'views/res_users_views.xml',
        # 'views/mrp_workcenter_views.xml',
        # 'views/mrp_workorder_views.xml',

        # 'views/mrp_workorder_portal_template.xml',
        # 'views/mrp_production_views.xml',
        'views/mrp_production_portal_template.xml',
        'views/approval_request_portal_template.xml',
        'views/menus.xml',
    ],
    # 'assets': {
    #     'web.assets_frontend': [
    #         'tiny_mrp/static/src/css/portal_css.scss',
    #     ],
    # },
    'application': True,
    'installable': True,
}
