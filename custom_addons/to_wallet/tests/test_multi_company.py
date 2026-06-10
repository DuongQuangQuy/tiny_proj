from odoo.exceptions import AccessError
from odoo.tests.common import tagged
from .common import TestWalletCommon


@tagged('post_install', '-at_install', 'xxx1')
class TestMultiCompany(TestWalletCommon):

    @classmethod
    def setUpClass(cls):
        super(TestMultiCompany, cls).setUpClass()
        # user_wallet_manager_1: Allowed Companies = Company 1
        cls.user_wallet_manager_1.write({'company_ids': cls.company_1.ids, 'company_id': cls.company_1.id})
        # user_wallet_manager_2: Allowed Companies = Company 2
        cls.user_wallet_manager_2.write({'company_ids': cls.company_2.ids, 'company_id': cls.company_2.id})
        # Wallet Type
        cls.wallet_type_company_1 = cls.env['wallet.type'].with_company(cls.company_1).create({'name': 'Wallet Type Company 1'})
        cls.wallet_type_company_2 = cls.env['wallet.type'].with_company(cls.company_2).create({'name': 'Wallet Type Company 2'})
        cls.wallet_type_common = cls.env['wallet.type'].create({'name': 'Wallet Type Company 1', 'company_id': False})
        # Wallet
        cls.wallet_company_1 = cls.partner.with_company(cls.company_1)._create_wallet_if_not_exist(
            wallet_type=cls.wallet_type_company_1
        )
        cls.wallet_company_2 = cls.partner.with_company(cls.company_2)._create_wallet_if_not_exist(
            wallet_type=cls.wallet_type_company_2
        )
        # Transaction History
        cls.wallet_history_company_1 = cls.env['wallet.history'].with_company(cls.company_1).create({'wallet_id': cls.wallet_company_1.id})
        cls.wallet_history_company_2 = cls.env['wallet.history'].with_company(cls.company_2).create({'wallet_id': cls.wallet_company_2.id})

    def test_01_access_rule_wallet_type_multi_company(self):
        with self.assertRaises(AccessError):
            self.wallet_type_company_1.with_user(self.user_wallet_manager_2).check_access_rule('read')
        with self.assertRaises(AccessError):
            self.wallet_type_company_2.with_user(self.user_wallet_manager_1).check_access_rule('read')
        self.wallet_type_company_1.with_user(self.user_wallet_manager_1).check_access_rule('read')
        self.wallet_type_common.with_user(self.user_wallet_manager_1).check_access_rule('read')
        self.wallet_type_company_2.with_user(self.user_wallet_manager_2).check_access_rule('read')
        self.wallet_type_common.with_user(self.user_wallet_manager_2).check_access_rule('read')
        self.wallet_type_company_1.with_user(self.user_admin).check_access_rule('read')
        self.wallet_type_company_2.with_user(self.user_admin).check_access_rule('read')
        self.wallet_type_common.with_user(self.user_admin).check_access_rule('read')

    def test_02_access_rule_wallet_multi_company(self):
        with self.assertRaises(AccessError):
            self.wallet_company_1.with_user(self.user_wallet_manager_2).check_access_rule('read')
        with self.assertRaises(AccessError):
            self.wallet_company_2.with_user(self.user_wallet_manager_1).check_access_rule('read')
        self.wallet_company_1.with_user(self.user_wallet_manager_1).check_access_rule('read')
        self.wallet_company_2.with_user(self.user_wallet_manager_2).check_access_rule('read')
        self.wallet_company_1.with_user(self.user_admin).check_access_rule('read')
        self.wallet_company_2.with_user(self.user_admin).check_access_rule('read')

    def test_03_access_rule_wallet_history_multi_company(self):
        with self.assertRaises(AccessError):
            self.wallet_history_company_1.with_user(self.user_wallet_manager_2).check_access_rule('read')
        with self.assertRaises(AccessError):
            self.wallet_history_company_2.with_user(self.user_wallet_manager_1).check_access_rule('read')
        self.wallet_history_company_1.with_user(self.user_wallet_manager_1).check_access_rule('read')
        self.wallet_history_company_2.with_user(self.user_wallet_manager_2).check_access_rule('read')
        self.wallet_history_company_1.with_user(self.user_admin).check_access_rule('read')
        self.wallet_history_company_2.with_user(self.user_admin).check_access_rule('read')
