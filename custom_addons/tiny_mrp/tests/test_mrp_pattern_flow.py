from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMrpPatternFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.workcenter_pattern = cls.env['mrp.workcenter'].create({
            'name': 'Rập test', 'code': 'TEST_RAP', 'is_pattern': True})
        cls.workcenter_sewing = cls.env['mrp.workcenter'].create({'name': 'May test', 'code': 'TEST_MAY'})
        cls.product = cls.env['product.product'].create({'name': 'Áo test', 'is_storable': True})
        cls.component = cls.env['product.product'].create({'name': 'Vải test', 'is_storable': True})

    def _create_production(self, operations):
        """Tạo MO nháp từ BOM có các công đoạn operations = [(tên, khu vực), ...]."""
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.product.product_tmpl_id.id,
            'product_qty': 1,
            'bom_line_ids': [(0, 0, {'product_id': self.component.id, 'product_qty': 1})],
            'operation_ids': [(0, 0, {
                'name': name,
                'workcenter_id': workcenter.id,
                'sequence': index,
            }) for index, (name, workcenter) in enumerate(operations)],
        })
        return self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1,
            'bom_id': bom.id,
        })

    def _workorder(self, production, name):
        return production.workorder_ids.filtered(lambda wo: wo.name == name)

    def test_01_pattern_operation_flow(self):
        production = self._create_production([('Cắt rập', self.workcenter_pattern), ('May', self.workcenter_sewing)])
        production.action_confirm()
        pattern_wo = self._workorder(production, 'Cắt rập')
        sewing_wo = self._workorder(production, 'May')

        self.assertFalse(production._get_children(), 'Rập là công đoạn, không được sinh MO con')
        self.assertFalse(production.is_mrp_pattern)
        self.assertTrue(pattern_wo.operation_id.is_pattern, 'Công đoạn lấy cờ rập từ khu vực sản xuất')
        self.assertTrue(pattern_wo.is_pattern)
        self.assertFalse(sewing_wo.is_pattern)
        self.assertTrue(production.has_pattern_workorder)
        self.assertTrue(production.need_pattern_confirm)
        self.assertFalse(production.pattern_workorders_done)

        # Rập chưa xong: May bị chặn, chưa xác nhận NVL rập và kho được
        with self.assertRaisesRegex(UserError, 'Công đoạn rập chưa hoàn thành'):
            sewing_wo.button_start(bypass=True)
        with self.assertRaisesRegex(UserError, 'Công đoạn rập chưa hoàn thành'):
            production.action_confirm_pattern()
        with self.assertRaisesRegex(UserError, 'rập và số lượng NVL'):
            production.action_confirm_stock()

        pattern_wo.button_start(bypass=True)
        self.assertEqual(production.state, 'progress')
        pattern_wo.button_finish()
        self.assertEqual(pattern_wo.state, 'done')
        self.assertTrue(production.pattern_workorders_done)

        # Rập xong nhưng chưa xác nhận NVL rập
        with self.assertRaisesRegex(UserError, 'Chưa xác nhận số lượng NVL sau rập'):
            sewing_wo.button_start(bypass=True)
        with self.assertRaisesRegex(UserError, 'rập và số lượng NVL'):
            production.action_confirm_stock()

        production.action_confirm_pattern()
        self.assertEqual(production.state_pattern, 'confirmed')

        # Đã xác nhận NVL rập nhưng kho chưa xác nhận
        with self.assertRaisesRegex(UserError, 'Kho chưa xác nhận'):
            sewing_wo.button_start(bypass=True)

        production.action_confirm_stock()
        self.assertEqual(production.state_stock, 'confirmed')
        self.assertFalse(sewing_wo._get_flow_block_reason())
        sewing_wo.button_start(bypass=True)
        self.assertEqual(sewing_wo.state, 'progress')

    def test_02_without_pattern_operation(self):
        production = self._create_production([('May', self.workcenter_sewing)])

        # MO còn nháp thì kho chưa được xác nhận
        with self.assertRaisesRegex(UserError, 'chưa được xác nhận'):
            production.action_confirm_stock()

        production.action_confirm()
        sewing_wo = self._workorder(production, 'May')

        self.assertFalse(production.has_pattern_workorder)
        self.assertFalse(production.need_pattern_confirm)
        self.assertTrue(production.pattern_workorders_done)

        with self.assertRaisesRegex(UserError, 'Kho chưa xác nhận'):
            sewing_wo.button_start(bypass=True)

        production.action_confirm_stock()
        self.assertEqual(production.state_stock, 'confirmed')
        self.assertEqual(production.state_pattern, 'draft', 'Lệnh không có rập thì bỏ qua bước xác nhận NVL rập')
        sewing_wo.button_start(bypass=True)
        self.assertEqual(sewing_wo.state, 'progress')
