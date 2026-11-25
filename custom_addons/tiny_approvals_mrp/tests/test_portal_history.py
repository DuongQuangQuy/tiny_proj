from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestPortalHistory(HttpCase):

    def setUp(self):
        super().setUp()
        groups = [self.env.ref('base.group_user').id, self.env.ref('mrp.group_mrp_user').id]
        self.worker = self.env['res.users'].create({
            'name': 'Thợ lịch sử', 'login': 'tiny_history_worker', 'password': 'tiny_history_worker',
            'group_ids': [(6, 0, groups)]})
        self.outsider = self.env['res.users'].create({
            'name': 'Thợ khác', 'login': 'tiny_history_outsider', 'password': 'tiny_history_outsider',
            'group_ids': [(6, 0, groups)]})
        workcenter = self.env['mrp.workcenter'].create({
            'name': 'May lịch sử', 'code': 'HIS_SEW', 'review_policy': 'none',
            'user_mrp_ids': [(6, 0, self.worker.ids)]})
        product = self.env['product.product'].create({'name': 'Túi lịch sử', 'is_storable': True})
        component = self.env['product.product'].create({'name': 'Vải lịch sử', 'is_storable': True})
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_qty': 1,
            'bom_line_ids': [(0, 0, {'product_id': component.id, 'product_qty': 1})],
            'operation_ids': [(0, 0, {'name': 'May lịch sử', 'workcenter_id': workcenter.id})],
        })
        production = self.env['mrp.production'].create({
            'product_id': product.id, 'product_qty': 1, 'bom_id': bom.id})
        production.action_confirm()
        production.action_confirm_stock()
        self.workorder = production.workorder_ids

    def test_01_history_list_and_detail(self):
        workorder = self.workorder
        workorder.button_start(bypass=True)
        end = fields.Datetime.now()
        vals = workorder._prepare_timeline_vals(0, end - timedelta(minutes=25), end)
        vals['user_mrp_id'] = self.worker.id
        self.env['mrp.workcenter.productivity'].create(vals)
        workorder.button_finish()
        self.assertEqual(workorder.state, 'done')

        self.authenticate('tiny_history_worker', 'tiny_history_worker')
        listing = self.url_open('/my/workorder-history')
        self.assertEqual(listing.status_code, 200)
        self.assertIn('May lịch sử', listing.text)
        self.assertIn(f'/my/workorder-history/{workorder.id}', listing.text)
        # Bộ lọc và tìm kiếm không lỗi
        self.assertEqual(self.url_open('/my/workorder-history?filterby=rework').status_code, 200)
        self.assertNotIn(f'/my/workorder-history/{workorder.id}',
                         self.url_open('/my/workorder-history?filterby=rework').text)
        self.assertIn(f'/my/workorder-history/{workorder.id}',
                      self.url_open('/my/workorder-history?search=Túi lịch sử').text)

        detail = self.url_open(f'/my/workorder-history/{workorder.id}')
        self.assertEqual(detail.status_code, 200)
        self.assertIn('Phiên làm việc của tôi', detail.text)
        self.assertIn('00:25', detail.text)

        home = self.url_open('/my/home')
        self.assertEqual(home.status_code, 200)

        # Người khác không xem được
        self.authenticate('tiny_history_outsider', 'tiny_history_outsider')
        self.assertEqual(self.url_open(f'/my/workorder-history/{workorder.id}').status_code, 404)
        self.assertNotIn(f'/my/workorder-history/{workorder.id}', self.url_open('/my/workorder-history').text)
