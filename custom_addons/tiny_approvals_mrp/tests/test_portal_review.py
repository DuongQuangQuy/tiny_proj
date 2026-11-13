import re
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestPortalReview(HttpCase):

    def setUp(self):
        super().setUp()
        groups = [self.env.ref('base.group_user').id, self.env.ref('mrp.group_mrp_user').id]
        self.reviewer = self.env['res.users'].create({
            'name': 'Quản lý xưởng portal', 'login': 'tiny_portal_reviewer', 'password': 'tiny_portal_reviewer',
            'group_ids': [(6, 0, groups)]})
        self.worker = self.env['res.users'].create({
            'name': 'Thợ vẽ portal', 'login': 'tiny_portal_worker', 'password': 'tiny_portal_worker',
            'group_ids': [(6, 0, groups)]})
        Workcenter = self.env['mrp.workcenter']
        self.wc_sew = Workcenter.create({
            'name': 'May portal', 'code': 'PRV_SEW', 'review_policy': 'optional', 'default_review_mode': 'before',
            'user_review_ids': [(6, 0, self.reviewer.ids)], 'user_mrp_ids': [(6, 0, self.worker.ids)]})
        self.wc_paint = Workcenter.create({
            'name': 'Vẽ portal', 'code': 'PRV_PAINT', 'review_policy': 'required',
            'user_review_ids': [(6, 0, self.reviewer.ids)], 'user_mrp_ids': [(6, 0, self.worker.ids)]})
        product = self.env['product.product'].create({'name': 'Túi portal', 'is_storable': True})
        component = self.env['product.product'].create({'name': 'Vải portal', 'is_storable': True})
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_qty': 1,
            'bom_line_ids': [(0, 0, {'product_id': component.id, 'product_qty': 1})],
            'operation_ids': [
                (0, 0, {'name': 'May', 'workcenter_id': self.wc_sew.id, 'sequence': 1}),
                (0, 0, {'name': 'Vẽ', 'workcenter_id': self.wc_paint.id, 'sequence': 2}),
            ],
        })
        self.production = self.env['mrp.production'].create({
            'product_id': product.id, 'product_qty': 1, 'bom_id': bom.id})
        self.production.action_confirm()
        self.production.action_confirm_stock()
        self.sew = self.production.workorder_ids.filtered(lambda wo: wo.name == 'May')
        self.paint = self.production.workorder_ids.filtered(lambda wo: wo.name == 'Vẽ')

    def _finish(self, workorder):
        workorder.button_start(bypass=True)
        end = fields.Datetime.now()
        self.env['mrp.workcenter.productivity'].create(
            workorder._prepare_timeline_vals(0, end - timedelta(minutes=10), end))
        workorder.button_finish()

    def _post(self, url, page_url, data):
        page = self.url_open(page_url)
        self.assertEqual(page.status_code, 200)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        return self.url_open(url, data=dict(data, csrf_token=token))

    def test_01_portal_review_flow(self):
        self._finish(self.sew)
        review = self.sew.last_review_id
        self.assertEqual(review.state, 'waiting')

        # Thợ không mở được trang duyệt
        self.authenticate('tiny_portal_worker', 'tiny_portal_worker')
        self.assertEqual(self.url_open(f'/my/reviews/{review.id}').status_code, 404)
        page = self.url_open(f'/my/workorders/{self.paint.id}')
        self.assertIn('chưa được duyệt đạt', page.text)

        self.authenticate('tiny_portal_reviewer', 'tiny_portal_reviewer')
        listing = self.url_open('/my/reviews')
        self.assertEqual(listing.status_code, 200)
        self.assertIn(f'/my/reviews/{review.id}', listing.text)
        detail_url = f'/my/reviews/{review.id}'
        action_url = f'{detail_url}/action'

        # Đạt khi chưa nhận duyệt: báo lỗi trên trang
        response = self._post(action_url, detail_url, {'action': 'pass'})
        self.assertIn('Nhận duyệt', response.text)
        self.assertEqual(review.state, 'waiting')

        self._post(action_url, detail_url, {'action': 'start'})
        self.assertEqual(review.state, 'reviewing')
        self.assertEqual(review.reviewer_id, self.reviewer)
        self._post(action_url, detail_url, {'action': 'pass'})
        self.assertEqual(review.state, 'passed')

        # Vẽ xong, chưa đạt và giao chỉnh lại cho thợ
        self._finish(self.paint)
        review_paint = self.paint.last_review_id
        detail_url = f'/my/reviews/{review_paint.id}'
        self._post(f'{detail_url}/action', detail_url, {'action': 'start'})
        defect = self.env.ref('tiny_approvals_mrp.mrp_reason_defect_pattern')
        self._post(f'{detail_url}/action', detail_url, {
            'action': 'fail', 'defect_reason_ids': str(defect.id), 'note': 'Sai màu',
            'return_workorder_id': str(self.paint.id)})
        self.assertEqual(review_paint.state, 'failed')
        self.assertTrue(self.paint.rework_return_id)

        self.authenticate('tiny_portal_worker', 'tiny_portal_worker')
        listing = self.url_open('/my/workorders')
        self.assertIn('Đang sửa', listing.text)
        page = self.url_open(f'/my/workorders/{self.paint.id}')
        self.assertIn('Sai họa tiết', page.text)
        self.assertIn('Sai màu', page.text)
        self.assertIn('Lịch sử duyệt', page.text)

    def test_02_portal_set_review_mode(self):
        self.authenticate('tiny_portal_reviewer', 'tiny_portal_reviewer')
        url = f'/my/productions/{self.production.id}'
        page = self.url_open(url)
        self.assertEqual(page.status_code, 200)
        self.assertIn('set_review_mode', page.text)
        self._post(f'{url}/action', url, {
            'action': 'set_review_mode', 'workorder_id': str(self.sew.id), 'review_mode': 'after'})
        self.assertEqual(self.sew.review_mode, 'after')
        self.assertEqual(self.sew.review_mode_user_id, self.reviewer)
        # Công đoạn bắt buộc duyệt không đổi được
        response = self._post(f'{url}/action', url, {
            'action': 'set_review_mode', 'workorder_id': str(self.paint.id), 'review_mode': 'after'})
        self.assertIn('không được chọn chế độ kiểm', response.text)
        self.assertEqual(self.paint.review_mode, 'before')
