from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestFitting(HttpCase):

    def setUp(self):
        super().setUp()
        self.admin = self.env.ref('base.user_admin')
        Workcenter = self.env['mrp.workcenter']
        self.wc_sew = Workcenter.create({
            'name': 'May fitting test', 'code': 'FT_SEW', 'user_mrp_ids': [(6, 0, self.admin.ids)]})
        self.wc_fit = Workcenter.create({
            'name': 'Thử fitting test', 'code': 'FT_FIT', 'user_mrp_ids': [(6, 0, self.admin.ids)]})
        # Fitting chọn khu vực của công ty khác cùng mã: vẫn phải nhận ra công đoạn thử
        other_company = self.env['res.company'].create({'name': 'Cty thương mại fitting test'})
        wc_other = Workcenter.with_company(other_company).create({
            'name': 'Thử (cty thương mại)', 'code': 'FT_FIT', 'company_id': other_company.id})
        self.trial = self.env['sale.trial'].create({'name': 'Thử lần 1 test', 'workcenter_id': wc_other.id})

        product = self.env['product.product'].create({'name': 'Áo fitting test', 'is_storable': True})
        component = self.env['product.product'].create({'name': 'Vải fitting test', 'is_storable': True})
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_qty': 1,
            'bom_line_ids': [(0, 0, {'product_id': component.id, 'product_qty': 1})],
            'operation_ids': [
                (0, 0, {'name': 'May', 'workcenter_id': self.wc_sew.id, 'sequence': 1}),
                (0, 0, {'name': 'Thử khách', 'workcenter_id': self.wc_fit.id, 'sequence': 2}),
            ],
        })
        partner = self.env['res.partner'].create({'name': 'Khách fitting test'})
        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'trial_id': self.trial.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 1})],
        })
        self.production = self.env['mrp.production'].create({
            'product_id': product.id, 'product_qty': 1, 'bom_id': bom.id,
            'sale_line_id': order.order_line.id,
            'user_mrp_stock_ids': [(6, 0, self.admin.ids)],
        })
        self.production.action_confirm()
        self.wo_sew = self.production.workorder_ids.filtered(lambda wo: wo.name == 'May')
        self.wo_fit = self.production.workorder_ids.filtered(lambda wo: wo.name == 'Thử khách')

    def test_01_fitting_on_production_and_workorders(self):
        self.assertEqual(self.production.trial_id, self.trial)
        self.assertTrue(self.wo_fit.is_fitting)
        self.assertFalse(self.wo_sew.is_fitting)

    def test_02_no_fitting_without_sale_order(self):
        production = self.env['mrp.production'].create({
            'product_id': self.production.product_id.id, 'product_qty': 1, 'bom_id': self.production.bom_id.id})
        production.action_confirm()
        self.assertFalse(production.trial_id)
        self.assertFalse(any(production.workorder_ids.mapped('is_fitting')))

    def test_03_trial_delivery_prefilled(self):
        action = self.production.action_create_trial_delivery()
        self.assertEqual(action['context']['default_trial_id'], self.trial.id)

    def test_04_report_shows_fitting(self):
        html, _type = self.env['ir.actions.report']._render_qweb_html(
            'tiny_sale_mrp.action_report_production_order_a5', self.production.ids)
        html = html.decode()
        self.assertIn('Thử lần 1 test', html)
        self.assertEqual(html.count('o_tpo_fitting_badge'), 1)

    def test_05_portal_shows_fitting(self):
        self.authenticate('admin', 'admin')
        page = self.url_open(f'/my/productions/{self.production.id}')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Thử lần 1 test', page.text)
        page = self.url_open(f'/my/workorders/{self.wo_fit.id}')
        self.assertEqual(page.status_code, 200)
        self.assertIn('o_wo_fitting_badge', page.text)
        page = self.url_open(f'/my/workorders/{self.wo_sew.id}')
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('o_wo_fitting_badge', page.text)
        # Danh sách chỉ hiện công đoạn của lệnh đã đến ngày bắt đầu và kho đã xác nhận
        self.production.date_start = fields.Datetime.now() - timedelta(hours=1)
        self.production.action_confirm_stock()
        page = self.url_open('/my/workorders')
        self.assertIn('Thử khách', page.text)
        self.assertEqual(page.text.count('o_wo_fitting_badge'), 1)
