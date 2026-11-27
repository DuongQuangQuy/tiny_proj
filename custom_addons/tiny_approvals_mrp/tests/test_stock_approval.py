import re

from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestStockApproval(HttpCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.is_mrp = True
        groups = [self.env.ref('base.group_user').id]
        self.stock_user = self.env['res.users'].create({
            'name': 'Kho test duyệt', 'login': 'tiny_stock_appr', 'password': 'tiny_stock_appr',
            'group_ids': [(6, 0, groups)], 'is_mrp_stock': True})
        self.other_user = self.env['res.users'].create({
            'name': 'Không phải kho', 'login': 'tiny_not_stock', 'password': 'tiny_not_stock',
            'group_ids': [(6, 0, groups)]})
        self.approver = self.env['res.users'].create({
            'name': 'Người duyệt test', 'login': 'tiny_approver', 'password': 'tiny_approver',
            'group_ids': [(6, 0, groups + [self.env.ref('approvals.group_approval_user').id])]})
        self.category = self.env['approval.category'].create({
            'name': 'Phê duyệt kho MRP test',
            'approval_type': 'mrp_stock',
            'company_id': self.company.id,
            'has_product': 'required',
            'has_quantity': 'required',
            'approver_ids': [(0, 0, {'user_id': self.approver.id})],
        })
        self.product = self.env['product.product'].create({'name': 'Vải bổ sung test', 'is_storable': True})

    def _post(self, url, page_url, data):
        page = self.url_open(page_url)
        self.assertEqual(page.status_code, 200)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        return self.url_open(url, data=dict(data, csrf_token=token))

    def _approver_messages(self, approval):
        return approval.message_ids.filtered(lambda m: self.approver.partner_id in m.partner_ids)

    def test_01_create_without_production_notifies_approver(self):
        self.authenticate('tiny_stock_appr', 'tiny_stock_appr')
        page = self.url_open('/my/approvals')
        self.assertIn('Phê duyệt bổ sung hàng', page.text)
        res = self._post('/my/approvals/create', '/my/approvals', {
            'product_ids[]': [self.product.id, ''],
            'descriptions[]': ['Mua thêm', ''],
            'quantities[]': ['2.5', '1'],
        })
        self.assertEqual(res.status_code, 200)
        approval = self.env['approval.request'].search([('request_owner_id', '=', self.stock_user.id)])
        self.assertEqual(len(approval), 1)
        self.assertFalse(approval.mrp_production_id)
        self.assertEqual(approval.request_status, 'pending')
        self.assertEqual(approval.product_line_ids.product_id, self.product)
        self.assertEqual(approval.product_line_ids.quantity, 2.5)
        self.assertEqual(len(self._approver_messages(approval)), 1)

    def test_02_not_stock_user_cannot_create(self):
        self.authenticate('tiny_not_stock', 'tiny_not_stock')
        page = self.url_open('/my/approvals')
        self.assertNotIn('Phê duyệt bổ sung hàng', page.text)
        # Trang này không có form cho người không phải kho: lấy csrf từ trang tài khoản
        res = self._post('/my/approvals/create', '/my/account', {
            'product_ids[]': [self.product.id], 'descriptions[]': [''], 'quantities[]': ['1']})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(self.env['approval.request'].search([('request_owner_id', '=', self.other_user.id)]))

    def test_03_empty_lines_rejected(self):
        self.authenticate('tiny_stock_appr', 'tiny_stock_appr')
        res = self._post('/my/approvals/create', '/my/approvals', {
            'product_ids[]': [''], 'descriptions[]': [''], 'quantities[]': ['1']})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(self.env['approval.request'].search([('request_owner_id', '=', self.stock_user.id)]))

    def test_04_backend_submit_notifies_approver(self):
        approval = self.env['approval.request'].create({
            'name': 'Phiếu backend',
            'category_id': self.category.id,
            'request_owner_id': self.stock_user.id,
            'product_line_ids': [(0, 0, {'product_id': self.product.id, 'quantity': 3})],
        })
        self.assertFalse(self._approver_messages(approval))
        approval.action_confirm()
        self.assertEqual(len(self._approver_messages(approval)), 1)
        # Đưa về nháp rồi nộp lại: người duyệt được nhắn lại
        approval.action_draft()
        approval.action_confirm()
        self.assertEqual(len(self._approver_messages(approval)), 2)
