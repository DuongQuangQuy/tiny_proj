from odoo.exceptions import AccessError
from odoo.tests.common import tagged
from .common import TestWalletCommon


@tagged('post_install', '-at_install', 'access_rights')
class TestAccessRight(TestWalletCommon):

    def test_01_access_right_internal_user(self):
        # Check read access right
        self.env['wallet'].with_user(self.user_internal).check_access_rights('read')
        self.env['wallet.type'].with_user(self.user_internal).check_access_rights('read')
        self.env['wallet.history'].with_user(self.user_internal).check_access_rights('read')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.user_internal).check_access_rights('create')
        with self.assertRaises(AccessError):
            self.env['wallet.type'].with_user(self.user_internal).check_access_rights('create')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.user_internal).check_access_rights('create')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.user_internal).check_access_rights('write')
        with self.assertRaises(AccessError):
            self.env['wallet.type'].with_user(self.user_internal).check_access_rights('write')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.user_internal).check_access_rights('write')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.user_internal).check_access_rights('unlink')
        with self.assertRaises(AccessError):
            self.env['wallet.type'].with_user(self.user_internal).check_access_rights('unlink')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.user_internal).check_access_rights('unlink')

    def test_02_access_right_portal_user(self):
        # Check read access right
        self.env['wallet'].with_user(self.portal_user).check_access_rights('read')
        self.env['wallet.type'].with_user(self.portal_user).check_access_rights('read')
        self.env['wallet.history'].with_user(self.portal_user).check_access_rights('read')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.portal_user).check_access_rights('create')
        with self.assertRaises(AccessError):
            self.env['wallet.type'].with_user(self.portal_user).check_access_rights('create')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.portal_user).check_access_rights('create')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.portal_user).check_access_rights('write')
        with self.assertRaises(AccessError):
            self.env['wallet.type'].with_user(self.portal_user).check_access_rights('write')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.portal_user).check_access_rights('write')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.portal_user).check_access_rights('unlink')
        with self.assertRaises(AccessError):
            self.env['wallet.type'].with_user(self.portal_user).check_access_rights('unlink')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.portal_user).check_access_rights('unlink')

    def test_03_access_right_wallet_manager(self):
        # Check read access right
        self.env['wallet'].with_user(self.user_wallet_manager_1).check_access_rights('read')
        self.env['wallet.type'].with_user(self.user_wallet_manager_1).check_access_rights('read')
        self.env['wallet.history'].with_user(self.user_wallet_manager_1).check_access_rights('read')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.user_wallet_manager_1).check_access_rights('create')
        with self.assertRaises(AccessError):
            self.env['wallet.type'].with_user(self.user_wallet_manager_1).check_access_rights('create')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.user_wallet_manager_1).check_access_rights('create')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.user_wallet_manager_1).check_access_rights('write')
        with self.assertRaises(AccessError):
            self.env['wallet.type'].with_user(self.user_wallet_manager_1).check_access_rights('write')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.user_wallet_manager_1).check_access_rights('write')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.user_wallet_manager_1).check_access_rights('unlink')
        with self.assertRaises(AccessError):
            self.env['wallet.type'].with_user(self.user_wallet_manager_1).check_access_rights('unlink')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.user_wallet_manager_1).check_access_rights('unlink')

    def test_04_access_right_account_readonly(self):
        # Check read access right
        self.env['wallet'].with_user(self.user_account_readonly).check_access_rights('read')
        self.env['wallet.type'].with_user(self.user_account_readonly).check_access_rights('read')
        self.env['wallet.history'].with_user(self.user_account_readonly).check_access_rights('read')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.user_account_readonly).check_access_rights('create')
        with self.assertRaises(AccessError):
            self.env['wallet.type'].with_user(self.user_account_readonly).check_access_rights('create')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.user_account_readonly).check_access_rights('create')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.user_account_readonly).check_access_rights('write')
        with self.assertRaises(AccessError):
            self.env['wallet.type'].with_user(self.user_account_readonly).check_access_rights('write')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.user_account_readonly).check_access_rights('write')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.user_account_readonly).check_access_rights('unlink')
        with self.assertRaises(AccessError):
            self.env['wallet.type'].with_user(self.user_account_readonly).check_access_rights('unlink')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.user_account_readonly).check_access_rights('unlink')

    def test_05_access_right_account_invoice(self):
        # Check read access right
        self.env['wallet'].with_user(self.user_account_invoice).check_access_rights('read')
        self.env['wallet.type'].with_user(self.user_account_invoice).check_access_rights('read')
        self.env['wallet.history'].with_user(self.user_account_invoice).check_access_rights('read')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.user_account_invoice).check_access_rights('create')
        with self.assertRaises(AccessError):
            self.env['wallet.type'].with_user(self.user_account_invoice).check_access_rights('create')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.user_account_invoice).check_access_rights('create')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.user_account_invoice).check_access_rights('write')
        with self.assertRaises(AccessError):
            self.env['wallet.type'].with_user(self.user_account_invoice).check_access_rights('write')
        self.env['wallet.history'].with_user(self.user_account_invoice).check_access_rights('write')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.user_account_invoice).check_access_rights('unlink')
        with self.assertRaises(AccessError):
            self.env['wallet.type'].with_user(self.user_account_invoice).check_access_rights('unlink')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.user_account_invoice).check_access_rights('unlink')

    def test_06_access_right_account_manager(self):
        # Check read access right
        self.env['wallet'].with_user(self.user_account_manager).check_access_rights('read')
        self.env['wallet.type'].with_user(self.user_account_manager).check_access_rights('read')
        self.env['wallet.history'].with_user(self.user_account_manager).check_access_rights('read')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.user_account_manager).check_access_rights('create')
        self.env['wallet.type'].with_user(self.user_account_manager).check_access_rights('create')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.user_account_manager).check_access_rights('create')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.user_account_manager).check_access_rights('write')
        self.env['wallet.type'].with_user(self.user_account_manager).check_access_rights('write')
        self.env['wallet.history'].with_user(self.user_account_manager).check_access_rights('write')
        # Check read access right
        with self.assertRaises(AccessError):
            self.env['wallet'].with_user(self.user_account_manager).check_access_rights('unlink')
        self.env['wallet.type'].with_user(self.user_account_manager).check_access_rights('unlink')
        with self.assertRaises(AccessError):
            self.env['wallet.history'].with_user(self.user_account_manager).check_access_rights('unlink')

    def test_07_own_access_rule_portal(self):
        portal_user1 = self.env['res.users'].create({
            'name': 'New Portal 1',
            'login': 'new_portal1',
            'email': 'new_portal1@example.viindoo.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]
        })
        portal_user2 = self.env['res.users'].create({
            'name': 'New Portal 2',
            'login': 'new_portal2',
            'email': 'new_portal2@example.viindoo.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]
        })
        # CHECK ACCESS WALLET
        wallet1 = portal_user1.partner_id._create_wallet_if_not_exist(self.wallet_type)
        wallet2 = portal_user2.partner_id._create_wallet_if_not_exist(self.wallet_type)
        # portal_user1 read wallet documents
        wallet1.with_user(portal_user1).check_access_rule('read')
        with self.assertRaises(AccessError):
            wallet1.with_user(portal_user2).check_access_rule('read')
        # portal_user2 read wallet documents
        wallet2.with_user(portal_user2).check_access_rule('read')
        with self.assertRaises(AccessError):
            wallet2.with_user(portal_user1).check_access_rule('read')
        # user_wallet_manager_1 read wallet documents
        wallet1.with_user(self.user_wallet_manager_1).check_access_rule('read')
        wallet2.with_user(self.user_wallet_manager_1).check_access_rule('read')

        # CHECK ACCESS WALLET HISTORY
        wallet_history1 = wallet1._create_wallet_history(amount=100, history_type='top-up')
        wallet_history2 = wallet2._create_wallet_history(amount=100, history_type='top-up')
        # portal_user1 read wallet histories
        wallet_history1.with_user(portal_user1).check_access_rule('read')
        with self.assertRaises(AccessError):
            wallet_history1.with_user(portal_user2).check_access_rule('read')
        # portal_user2 read wallet histories
        wallet_history2.with_user(portal_user2).check_access_rule('read')
        with self.assertRaises(AccessError):
            wallet_history2.with_user(portal_user1).check_access_rule('read')
        # user_wallet_manager_1 read wallet histories
        wallet_history1.with_user(self.user_wallet_manager_1).check_access_rule('read')
        wallet_history2.with_user(self.user_wallet_manager_1).check_access_rule('read')

    def test_08_own_access_rule_internal(self):
        internal_user1 = self.env['res.users'].create({
            'name': 'New Internal User 1',
            'login': 'new_internal1',
            'email': 'new_internal1@example.viindoo.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]
        })
        internal_user2 = self.env['res.users'].create({
            'name': 'New Internal User 2',
            'login': 'new_internal2',
            'email': 'new_internal2@example.viindoo.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]
        })
        # CHECK ACCESS WALLET
        wallet1 = internal_user1.partner_id._create_wallet_if_not_exist(self.wallet_type)
        wallet2 = internal_user2.partner_id._create_wallet_if_not_exist(self.wallet_type)
        # portal_user1 read wallet documents
        wallet1.with_user(internal_user1).check_access_rule('read')
        with self.assertRaises(AccessError):
            wallet1.with_user(internal_user2).check_access_rule('read')
        # portal_user2 read wallet documents
        wallet2.with_user(internal_user2).check_access_rule('read')
        with self.assertRaises(AccessError):
            wallet2.with_user(internal_user1).check_access_rule('read')
        # user_wallet_manager_1 read wallet documents
        wallet1.with_user(self.user_wallet_manager_1).check_access_rule('read')
        wallet2.with_user(self.user_wallet_manager_1).check_access_rule('read')

        # CHECK ACCESS WALLET HISTORY
        wallet_history1 = wallet1._create_wallet_history(amount=100, history_type='top-up')
        wallet_history2 = wallet2._create_wallet_history(amount=100, history_type='top-up')
        # portal_user1 read wallet histories
        wallet_history1.with_user(internal_user1).check_access_rule('read')
        with self.assertRaises(AccessError):
            wallet_history1.with_user(internal_user2).check_access_rule('read')
        # portal_user2 read wallet histories
        wallet_history2.with_user(internal_user2).check_access_rule('read')
        with self.assertRaises(AccessError):
            wallet_history2.with_user(internal_user1).check_access_rule('read')
        # user_wallet_manager_1 read wallet histories
        wallet_history1.with_user(self.user_wallet_manager_1).check_access_rule('read')
        wallet_history2.with_user(self.user_wallet_manager_1).check_access_rule('read')
