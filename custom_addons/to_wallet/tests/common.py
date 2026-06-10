import datetime
from odoo.tests import tagged
from odoo.fields import Command

from odoo.addons.account_payment.tests.common import AccountPaymentCommon


@tagged('post_install', '-at_install')
class TestWalletCommon(AccountPaymentCommon):

    @classmethod
    def setUpClass(cls):
        super(TestWalletCommon, cls).setUpClass()

        cls.env = cls.env(su=True, context=dict(cls.env.context, tracking_disable=True))
        cls.cr = cls.env.cr

        # Setup multi company
        cls.company_1 = cls.company_data['company']
        cls.company_2 = cls.company_data_2['company']

        # Setup multi currency
        cls.currency_vnd = cls.env.ref('base.VND')
        cls.currency_usd = cls.env.ref('base.USD')
        cls.currency_eur = cls.env.ref('base.EUR')
        (cls.currency_vnd + cls.currency_usd + cls.currency_eur).active = True

        cls.current_year = datetime.date.today().year

        # ==== Setup currency rate ==== #
        # Company currency: USD
        cls.env['res.currency.rate'].create([
            {
                'name': datetime.date(cls.current_year - 1, 1, 1),
                'inverse_company_rate': 25000,
                'currency_id': cls.currency_vnd.id
            }, {
                'name': datetime.date(cls.current_year - 1, 1, 1),
                'inverse_company_rate': 1.1,
                'currency_id': cls.currency_eur.id
            }, {
                'name': datetime.date(cls.current_year + 1, 1, 1),
                'inverse_company_rate': 1.2,
                'currency_id': cls.currency_eur.id
            }
        ])

        # Setup product
        cls.product = cls.env['product.product'].create({
            'name': 'Product',
            'type': 'service'
        })
        cls.product_category_all = cls.env.ref('product.product_category_all')

        # Setup journal
        cls.bank_journal_usd = cls.env['account.journal'].create({
            'name': 'Bank USD',
            'type': 'bank',
            'code': 'BNKUSD',
            'currency_id': cls.currency_usd.id
        })
        cls.bank_journal_vnd = cls.env['account.journal'].create({
            'name': 'Bank VND',
            'type': 'bank',
            'code': 'BNKVN',
            'currency_id': cls.currency_vnd.id
        })
        cls.bank_journal_eur = cls.env['account.journal'].create({
            'name': 'Bank EUR',
            'type': 'bank',
            'code': 'BNKEUR',
            'currency_id': cls.currency_eur.id
        })
        cls.account_payment_method_manual_in = cls.env.ref('account.account_payment_method_manual_in')

        # Setup account
        cls.account_income = cls.product_category_all.property_account_income_categ_id

        cls.account_112 = cls.env['account.account'].create({
            'name': 'Tien gui ngan hang',
            'code': 112001,
            'account_type': 'asset_cash',
        })
        cls.account_131 = cls.env['account.account'].create({
            'name': 'Phai thu cua KH',
            'code': 131001,
            'account_type': 'asset_receivable',
            'reconcile': True
        })
        cls.account_1125 = cls.env['account.account'].create({
            'name': 'Outstanding Receipts',
            'code': 1125001,
            'account_type': 'asset_current',
            'reconcile': True,
        })
        cls.account_1126 = cls.env['account.account'].create({
            'name': 'Outstanding Payments',
            'code': 1126001,
            'account_type': 'asset_current',
            'reconcile': True
        })

        # Setup user/partner
        cls.partner = cls.env['res.partner'].create({
            'name': 'Ngoc',
            'parent_id': cls.company.partner_id.id
        })

        cls.portal_user = cls.env['res.users'].create({
            'name': 'New Portal User',
            'login': 'newportaluser',
            'password': 'newportaluser',
            'email': 'newportal1@example.viindoo.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])]
        })

        cls.user_internal = cls.env['res.users'].create({
            'name': 'User Internal',
            'login': 'wallet_internal',
            'email': 'internal@example.viindoo.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])]
        })
        cls.user_wallet_manager_1 = cls.env['res.users'].create({
            'name': 'User Wallet Manager No.1',
            'login': 'wallet_manager1',
            'email': 'wallet_manager1@example.viindoo.com',
            'groups_id': [(6, 0, [cls.env.ref('to_wallet.group_wallet_manager').id])],
        })
        cls.user_wallet_manager_2 = cls.env['res.users'].create({
            'name': 'User Wallet Manager No.2',
            'login': 'wallet_manager2',
            'email': 'wallet_manager2@example.viindoo.com',
            'groups_id': [(6, 0, [cls.env.ref('to_wallet.group_wallet_manager').id])],
        })
        cls.user_account_readonly = cls.env['res.users'].create({
            'name': 'User Account Readonly',
            'login': 'account_readonly',
            'email': 'account_readonly@example.viindoo.com',
            'groups_id': [(6, 0, [cls.env.ref('account.group_account_readonly').id])],
        })
        cls.user_account_invoice = cls.env['res.users'].create({
            'name': 'User Account Invoice',
            'login': 'account_invoice',
            'email': 'account_invoice@example.viindoo.com',
            'groups_id': [(6, 0, [cls.env.ref('account.group_account_invoice').id])],
        })
        cls.user_accountant = cls.env['res.users'].create({
            'name': 'User Accountant',
            'login': 'accountant',
            'email': 'accountant@example.viindoo.com',
            'groups_id': [(6, 0, [cls.env.ref('account.group_account_user').id])],
        })
        cls.user_account_manager = cls.env['res.users'].create({
            'name': 'User Account Manager',
            'login': 'account_admin',
            'email': 'account_admin@example.viindoo.com',
            'groups_id': [(6, 0, [cls.env.ref('account.group_account_manager').id])],
        })
        cls.user_admin = cls.env.ref('base.user_admin')
        cls.user_admin.write(
            {
                'company_ids': [(4, cls.company_1.id), (4, cls.company_2.id)],
                'groups_id': [(6, 0, [cls.env.ref('base.group_multi_company').id])]
            }
        )

        # Setup provider
        cls.wallet_provider = cls.env.ref('to_wallet.payment_provider_company_wallet')
        cls.wallet_payment_method = cls.env.ref('to_wallet.payment_method_wallet')

        # Setup wallet type
        cls.reward_wallet_type = cls.env.ref('to_wallet.reward_wallet_type')
        cls.consumption_wallet_type = cls.env.ref('to_wallet.consumption_wallet_type')
        cls.wallet_type = cls.env['wallet.type'].create({'name': 'Wallet Type (Test)'})

        # Setup Portal wallet
        cls.portal_user_wallet = cls.portal_user.partner_id._create_wallet_if_not_exist(cls.wallet_type, cls.currency_usd)

    def setUp(self):
        self.enable_reconcile_after_done_patcher = False
        super().setUp()

    @classmethod
    def create_payment(cls, **custom_vals):
        vals = {
            'amount': 0,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': cls.partner.id,
            'payment_method_id': cls.account_payment_method_manual_in.id,
            'journal_id': cls.bank_journal_usd.id,
            'date': datetime.date(cls.current_year - 1, 1, 1)
        }
        vals.update(custom_vals)
        payment = cls.env['account.payment'].create(vals)
        payment.action_post()
        return payment

    @classmethod
    def create_invoice(cls, custom_vals=None, custom_line_vals_list=None, post_invoice=True):
        if custom_vals is None:
            custom_vals = {}
        if custom_line_vals_list is None:
            custom_line_vals_list = []
        line_vals_list = []
        for custom_line_vals in custom_line_vals_list:
            line_vals = {
                'product_id': cls.product.id,
                'name': cls.product.name,
                'price_unit': 0,
                'account_id': cls.account_income.id,
                'tax_ids': [Command.clear()],
            }
            line_vals.update(custom_line_vals)
            line_vals_list.append(line_vals)
        vals = {
            'move_type': 'out_invoice',
            'partner_id': cls.partner.id,
            'invoice_line_ids': [(0, 0, vals) for vals in line_vals_list],
            'date': datetime.date(cls.current_year - 1, 1, 1),
            'invoice_date': datetime.date(cls.current_year - 1, 1, 1),
            'currency_id': cls.currency_usd.id
        }
        vals.update(custom_vals)
        invoice = cls.env['account.move'].create(vals)
        if post_invoice:
            invoice.action_post()
        return invoice

    def reconcile_payment_vs_invoice(self, payment, invoice, force_pay_by_wallet=False):
        move_lines = payment.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        for line in move_lines:
            invoice.with_context(force_pay_by_wallet=force_pay_by_wallet).js_assign_outstanding_line(line.id)

    def reconcile_wallet_vs_invoice(self, wallet_type, invoice):
        ctx = dict(active_model='account.move', active_ids=invoice.ids)
        wizard = self.env['wallet.payment.wizard'].with_context(**ctx).create({'wallet_type_id': wallet_type.id})
        action = wizard.acction_process()
        return self.env['wallet.history'].browse(action['res_id'])
