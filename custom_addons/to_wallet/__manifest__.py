{
    'name': "E-Wallet",
    'name_vi_VN': 'Ví điện tử',
    'summary': "Manage commercial partners' e-wallets",
    'summary_vi_VN': 'Quản lý ví điện tử của đối tác thương mại',
    'description': """
Demo video: `eWallet <https://youtu.be/PRkL1j91QAk>`_

Description
===========
E-Wallet is a tool to support payment transactions for products and services, cashback transactions, storing, transferring, withdrawing, and depositing money, etc.
However, businesses may face difficulties in setting up and managing Customers' e-Wallets without an effective management tool.

Key Features
============

* Allow businesses to set up e-Wallet payment transactions for products sold.
* Help businesses record and track the status of Customers' e-Wallets; provide multi-currency feature to support recording different foreign currency values.
* Allow businesses to record and track Quotations>Sales Orders>Invoices paid by Customers' e-Wallets.
* Support businesses to monitor all accounts relating to a Company Customer and link transactions from these accounts to that company’s e-Wallet.
* Allow Customers with Portal User access to track their e-Wallets on the system.
* Provide evidence for bank statements and bank reconciliation.

Visit the Documentation for detailed Instructions with image and video descriptions.

Supported Editions
==================
1. Community Edition
2. Enterprise Edition

    """,

    'description_vi_VN': """
Demo video: `Ví điện tử <https://youtu.be/PRkL1j91QAk>`_

Mô tả
=====
Ví điện tử là công cụ hỗ trợ các giao dịch thanh toán sản phẩm và dịch vụ, giao dịch hoàn tiền, lưu trữ, chuyển, rút và nạp tiền,....
Tuy nhiên, doanh nghiệp có thể gặp khó khăn trong việc thiết lập và quản lý Ví điện tử của Khách hàng nếu không có công cụ quản lý hiệu quả.

Tính năng
=========

* Cho phép doanh nghiệp thiết lập giao dịch thanh toán bằng Ví điện tử cho sản phẩm bán.
* Giúp doanh nghiệp ghi nhận và theo dõi trạng thái Ví điện tử của Khách hàng; hỗ trợ đa tiền tệ cho các giá trị ngoại tệ khác nhau.
* Cho phép doanh nghiệp ghi nhận và theo dõi Báo giá>Đơn bán>Hóa đơn được thanh toán bằng Ví điện tử của Khách hàng.
* Hỗ trợ doanh nghiệp theo dõi và liên kết các giao dịch từ các tài khoản liên quan đến Ví điện tử của một Khách hàng doanh nghiệp.
* Cho phép Khách hàng có quyền Người dùng cổng thông tin theo dõi Ví điện tử của mình trên hệ thống.
* Hỗ trợ thực hiện sao kê và đối chiếu sao kê.

Truy cập Tài liệu hướng dẫn để xem Hướng dẫn chi tiết với mô tả bằng hình ảnh và video.

Ấn bản được Hỗ trợ
==================
1. Ấn bản Community
2. Ấn bản Enterprise

    """,

    'author': "T.V.T Marine Automation (aka TVTMA),Viindoo",
    'website': "https://viindoo.com/apps/app/17.0/to_wallet",
    'live_test_url': "https://v17demo-int.viindoo.com",
    'live_test_url_vi_VN': "https://v17demo-vn.viindoo.com",
    'demo_video_url': "https://youtu.be/PRkL1j91QAk",
    'support': "apps.support@viindoo.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Accounting/Accounting',
    'version': '0.5.2',

    # any module necessary for this one to work correctly
    'depends': ['account_payment',],

    # always loaded
    'data': [
        'security/module_security.xml',
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'wizard/wallet_payment_wizard_views.xml',
        'wizard/account_payment_register_views.xml',
        'wizard/wallet_payment_creation_wizard_views.xml',
        'views/account_invoice_views.xml',
        'views/account_move_line_views.xml',
        'views/account_payment_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'views/wallet_portal_templates.xml',
        'views/wallet_views.xml',
        'views/wallet_type_views.xml',
        'views/wallet_history_views.xml',
        'views/wallet_payment_templates.xml',
        'data/payment_provider_data.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/wallet_type_demo.xml',
    ],
    'images': [
        'static/description/main_screenshot.png'
    ],
    'assets': {
        'web.assets_frontend': [
            'to_wallet/static/src/js/*.js',
            'to_wallet/static/src/xml/*.xml',
            'to_wallet/static/src/scss/*.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': True,
    'price': 45.9,
    'subscription_price': 41.38,
    'currency': 'EUR',
    'license': 'OPL-1',
}
