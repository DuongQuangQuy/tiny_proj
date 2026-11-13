import re

from odoo.exceptions import UserError
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestPortalProduction(HttpCase):

    def test_01_portal_production_stock_on_hand(self):
        """Trang portal lệnh sản xuất hiện cột tồn kho thực tế của từng thành phần."""
        admin = self.env.ref('base.user_admin')
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        product = self.env['product.product'].create({'name': 'Áo test portal', 'is_storable': True})
        enough = self.env['product.product'].create({'name': 'Vải đủ test', 'is_storable': True})
        missing = self.env['product.product'].create({'name': 'Vải thiếu test', 'is_storable': True})
        self.env['stock.quant']._update_available_quantity(enough, warehouse.lot_stock_id, 10)
        self.env['stock.quant']._update_available_quantity(missing, warehouse.lot_stock_id, 1)
        production = self.env['mrp.production'].create({
            'product_id': product.id,
            'product_qty': 1,
            'picking_type_id': warehouse.manu_type_id.id,
            'user_mrp_stock_ids': [(6, 0, admin.ids)],
            'move_raw_ids': [
                (0, 0, {'product_id': enough.id, 'product_uom_qty': 3}),
                (0, 0, {'product_id': missing.id, 'product_uom_qty': 2}),
            ],
        })
        production.action_confirm()

        self.authenticate('admin', 'admin')
        response = self.url_open(f'/my/productions/{production.id}')
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn('Tồn kho thực tế', html)

        def row_text(name):
            row = html[html.index(name):]
            row = row[:row.index('</tr>')]
            return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', row))

        # Đủ hàng: tồn 10 >= cần 3, hiện màu xanh
        self.assertIn('10.00', row_text('Vải đủ test'))
        self.assertIn('text-success', html[html.index('Vải đủ test'):html.index('Vải thiếu test')])
        # Thiếu hàng: tồn 1 < cần 2, hiện màu đỏ
        self.assertIn('1.00', row_text('Vải thiếu test'))
        missing_row = html[html.index('Vải thiếu test'):]
        self.assertIn('text-danger', missing_row[:missing_row.index('</tr>')])

    def _create_production_with_operations(self, operations):
        """MO đã xác nhận, kho đã xác nhận, các công đoạn giao cho admin. operations = [(tên, là công đoạn rập)]."""
        admin = self.env.ref('base.user_admin')
        product = self.env['product.product'].create({'name': 'Áo pass test', 'is_storable': True})
        component = self.env['product.product'].create({'name': 'Vải pass test', 'is_storable': True})
        operation_vals = []
        for index, (name, is_pattern) in enumerate(operations):
            workcenter = self.env['mrp.workcenter'].create({
                'name': f'Khu {name}', 'code': f'PASS_{index}', 'is_pattern': is_pattern,
                'user_mrp_ids': [(6, 0, admin.ids)]})
            operation_vals.append((0, 0, {'name': name, 'workcenter_id': workcenter.id, 'sequence': index}))
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_qty': 1,
            'bom_line_ids': [(0, 0, {'product_id': component.id, 'product_qty': 1})],
            'operation_ids': operation_vals,
        })
        production = self.env['mrp.production'].create({
            'product_id': product.id, 'product_qty': 1, 'bom_id': bom.id})
        production.action_confirm()
        return production

    def test_02_portal_pass_workorder(self):
        """Nút Pass trên portal hoàn thành công đoạn ngay, không ghi giờ làm và đánh dấu không tính KPI."""
        production = self._create_production_with_operations([('Thêu', False), ('May', False)])
        production.action_confirm_stock()
        workorder = production.workorder_ids.filtered(lambda wo: wo.name == 'Thêu')

        self.authenticate('admin', 'admin')
        page = self.url_open(f'/my/workorders/{workorder.id}')
        self.assertIn('Pass (có sẵn)', page.text)

        csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        response = self.url_open(f'/my/workorders/{workorder.id}/action',
                                 data={'action': 'pass', 'csrf_token': csrf_token})
        self.assertEqual(response.status_code, 200)
        workorder.invalidate_recordset()
        self.assertEqual(workorder.state, 'done')
        self.assertTrue(workorder.is_passed)
        self.assertFalse(workorder.time_ids, 'Pass không được ghi giờ làm')
        self.assertIn('Pass', self.url_open(f'/my/workorders/{workorder.id}').text)
        # Công đoạn còn lại vẫn làm bình thường, không bị đánh dấu pass
        self.assertFalse((production.workorder_ids - workorder).is_passed)

    def test_03_pass_respects_flow(self):
        """Không pass được khi quy trình chưa cho phép (kho chưa xác nhận)."""
        production = self._create_production_with_operations([('May', False)])
        workorder = production.workorder_ids
        with self.assertRaises(UserError):
            workorder.action_pass()
        self.assertFalse(workorder.is_passed)
        self.assertNotEqual(workorder.state, 'done')

    def test_04_pass_pattern_workorder(self):
        """Công đoạn rập có sẵn được pass, sau đó lệnh coi như rập đã xong."""
        production = self._create_production_with_operations([('Rập', True), ('May', False)])
        pattern = production.workorder_ids.filtered('is_pattern')
        pattern.action_pass()
        self.assertTrue(pattern.is_passed)
        self.assertTrue(production.pattern_workorders_done)
