# -*- coding: utf-8 -*-

{
    'name': "Tiny: Approvals Mrp",
    'summary': "Tiny: Approvals Mrp",
    'description': "Tiny: Approvals Mrp. Duyệt công đoạn, trả lại công đoạn, tách giờ làm mới / giờ sửa.",
    'author': "Tiny",
    'website': "https://tiny.com.vn/",
    'category': 'Approvals/Mrp',
    'version': '19.0.0.1',
    'license': 'LGPL-3',
    'depends': [
        'base', 'mail', 'tiny_mrp', 'approvals', 'tiny_contacts'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/mrp_reason_data.xml',
        'views/mrp_review_config_views.xml',
        'views/mrp_workorder_review_views.xml',
        'views/mrp_production_portal_template.xml',
        'views/approval_request_portal_template.xml',
        'views/mrp_review_portal_template.xml',
        'views/menus.xml',
    ],
    'application': True,
    'installable': True,
}
