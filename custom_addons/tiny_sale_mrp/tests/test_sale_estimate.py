from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestSaleEstimate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # Excel tính theo VND nên dùng VND cho 2 công ty để kiểm tra quy đổi USD
        cls.vnd = env.ref('base.VND')
        cls.vnd.active = True
        cls.usd = env.ref('base.USD')
        cls.usd.active = True
        cls.service_company = env['res.company'].create({
            'name': 'Tiny Thuong Mai', 'is_service': True, 'currency_id': cls.vnd.id})
        cls.mrp_company = env['res.company'].create({
            'name': 'Tiny San Xuat', 'is_mrp': True, 'currency_id': cls.vnd.id})
        env['res.company'].search([
            ('is_mrp', '=', True), ('id', '!=', cls.mrp_company.id)]).is_mrp = False

        service_wh = env['stock.warehouse'].search([('company_id', '=', cls.service_company.id)], limit=1)
        mrp_wh = env['stock.warehouse'].search([('company_id', '=', cls.mrp_company.id)], limit=1)
        mto_route = env.ref('stock.route_warehouse0_mto').sudo()
        mto_route.active = True
        cls.service_company.estimate_route_ids = mto_route | service_wh.buy_pull_id.route_id

        mrp_route = mrp_wh.manufacture_pull_id.route_id
        mrp_route.write({
            'is_mrp': True,
            'sale_selectable': True,
            'rule_ids': [Command.create({
                'name': 'Giao tu kho SX theo MTO',
                'action': 'pull',
                'procure_method': 'make_to_order',
                'location_src_id': mrp_wh.lot_stock_id.id,
                'location_dest_id': env.ref('stock.stock_location_customers').id,
                'picking_type_id': mrp_wh.out_type_id.id,
                'company_id': cls.mrp_company.id,
            })],
        })

        cls.fabric = env['product.product'].create({
            'name': 'Vai A', 'type': 'consu', 'is_storable': True, 'company_id': False})
        cls.fabric.with_company(cls.mrp_company).standard_price = 100000
        cls.fabric.with_company(cls.service_company).standard_price = 1
        cls.workcenter = env['mrp.workcenter'].with_company(cls.mrp_company).create({
            'name': 'May', 'code': 'MAY', 'company_id': cls.mrp_company.id, 'costs_hour': 60000})
        cls.service_workcenter = env['mrp.workcenter'].with_company(cls.service_company).create({
            'name': 'May TM', 'code': 'MAY', 'company_id': cls.service_company.id, 'costs_hour': 1})
        cls.other_workcenter = env['mrp.workcenter'].with_company(cls.service_company).create({
            'name': 'Xuong khac', 'code': 'KHAC', 'company_id': cls.service_company.id})
        cls.customer = env['res.partner'].create({'name': 'Khach le'})
        cls.salesman = new_test_user(
            env, login='estimate_sales', groups='sales_team.group_sale_salesman',
            company_id=cls.service_company.id, company_ids=[Command.set(cls.service_company.ids)])

    def _create_estimate(self):
        env = self.env(user=self.salesman, context={'allowed_company_ids': self.service_company.ids})
        return env['sale.estimate'].with_company(self.service_company).create({
            'partner_id': self.customer.id,
            'line_ids': [Command.create({
                'name': 'Sofa may do',
                'product_qty': 2,
                'product_size': '2m x 1m',
                'code_fabric': self.fabric.id,
                'note': 'Theo yeu cau',
                'extra_cost': 50000,
                'bom_line_ids': [Command.create({'product_id': self.fabric.id, 'product_qty': 3})],
                'operation_ids': [Command.create({'workcenter_id': self.service_workcenter.id, 'time_cycle_manual': 30})],
            })],
        })

    def test_01_cost_uses_manufacturing_company(self):
        estimate = self._create_estimate()
        line = estimate.line_ids
        self.assertEqual(line.bom_line_ids.cost_unit, 100000)
        self.assertEqual(line.operation_ids.name, 'May TM')
        self.assertEqual(line.operation_cost, 30000)
        self.assertEqual(line.cost_unit, 380000)
        # Mặc định LV2 x 1,9: (380.000 x 2) x 1,25 x 1,9 = 1.805.000, làm tròn 100.000
        self.assertEqual(line.price_unit, 1800000)
        self.assertEqual(estimate.amount_total, 3600000)
        self.assertEqual(estimate.amount_margin, 2840000)

    def test_01b_cost_falls_back_to_estimate_company(self):
        # NVL chưa có giá vốn ở công ty sản xuất: lấy giá vốn công ty trên phiếu
        lining = self.env['product.product'].create({
            'name': 'Lot B', 'type': 'consu', 'is_storable': True, 'company_id': False})
        lining.with_company(self.service_company).standard_price = 45000
        env = self.env(user=self.salesman, context={'allowed_company_ids': self.service_company.ids})
        form = Form(env['sale.estimate'])
        form.partner_id = self.customer
        with form.line_ids.new() as line:
            line.name = 'Ghe may do'
            with line.bom_line_ids.new() as bom_line:
                bom_line.product_id = lining
                self.assertEqual(bom_line.cost_unit, 45000)
            with line.bom_line_ids.new() as bom_line:
                # Đã có giá ở công ty sản xuất thì vẫn ưu tiên giá đó
                bom_line.product_id = self.fabric
                self.assertEqual(bom_line.cost_unit, 100000)
        estimate = form.save()
        self.assertEqual(sorted(estimate.line_ids.bom_line_ids.mapped('cost_unit')), [45000, 100000])

    def test_02_create_order_builds_product_and_bom(self):
        estimate = self._create_estimate()
        estimate.action_create_sale_order()
        line = estimate.sudo().line_ids
        bom = line.bom_id
        self.assertEqual(estimate.state, 'ordered')
        self.assertFalse(line.product_id.company_id)
        self.assertEqual(bom.company_id, self.mrp_company)
        self.assertEqual(bom.bom_line_ids.product_id, self.fabric)
        self.assertEqual(bom.bom_line_ids.product_qty, 3)
        self.assertEqual(bom.operation_ids.workcenter_id, self.workcenter)
        self.assertEqual(bom.operation_ids.time_cycle_manual, 30)
        self.assertEqual(line.product_id.code_fabric, self.fabric)
        self.assertEqual(line.product_id.seller_ids.partner_id, self.mrp_company.partner_id)
        self.assertEqual(line.product_id.seller_ids.price, 380000)
        self.assertEqual(line.product_id.with_company(self.mrp_company).standard_price, 380000)
        order_line = estimate.sale_order_id.sudo().order_line
        self.assertEqual(order_line.price_unit, 1800000)
        self.assertEqual(order_line.product_uom_qty, 2)
        self.assertEqual(order_line.product_size, '2m x 1m')
        self.assertEqual(order_line.code_fabric, self.fabric)

    def test_03_full_flow_reaches_manufacturing_order(self):
        estimate = self._create_estimate()
        estimate.action_create_sale_order()
        order = estimate.sudo().sale_order_id
        order.with_company(self.service_company).action_confirm()

        purchase = order._get_purchase_orders()
        self.assertEqual(purchase.partner_id, self.mrp_company.partner_id)
        self.assertEqual(purchase.state, 'purchase')
        self.assertEqual(purchase.order_line.price_unit, 380000)
        mrp_order = self.env['sale.order'].sudo().search([('origin', '=', purchase.name)])
        self.assertEqual(mrp_order.company_id, self.mrp_company)
        self.assertEqual(mrp_order.order_line.product_size, '2m x 1m')

        production = self.env['mrp.production'].sudo().search([('product_id', '=', order.order_line.product_id.id)])
        self.assertEqual(production.bom_id, estimate.sudo().line_ids.bom_id)
        self.assertEqual(production.company_id, self.mrp_company)
        self.assertEqual(production.product_qty, 2)
        self.assertEqual(production.move_raw_ids.product_id, self.fabric)
        self.assertEqual(production.move_raw_ids.product_uom_qty, 6)
        self.assertEqual(production.workorder_ids.workcenter_id, self.workcenter)
        self.assertEqual(production.workorder_ids.name, 'May TM')

    def test_04_reopen_replaces_bom_and_reuses_product(self):
        estimate = self._create_estimate()
        estimate.action_create_sale_order()
        line = estimate.line_ids
        product, old_bom = line.product_id, line.sudo().bom_id
        with self.assertRaises(UserError):
            estimate.action_reset_draft()
        estimate.sudo().sale_order_id.with_company(self.service_company).action_cancel()
        estimate.action_reset_draft()
        self.assertEqual(estimate.state, 'draft')

        line.bom_line_ids.product_qty = 5
        estimate.action_create_sale_order()
        self.assertEqual(line.product_id, product)
        self.assertFalse(old_bom.active)
        self.assertEqual(line.sudo().bom_id.bom_line_ids.product_qty, 5)
        self.assertEqual(len(product.sudo().seller_ids), 1)
        self.assertEqual(product.sudo().seller_ids.price, 580000)

    def test_05_copy_keeps_bom_lines_but_not_created_records(self):
        estimate = self._create_estimate()
        estimate.action_create_sale_order()
        duplicate = estimate.copy()
        self.assertEqual(duplicate.state, 'draft')
        self.assertEqual(duplicate.line_ids.bom_line_ids.product_id, self.fabric)
        self.assertEqual(duplicate.line_ids.operation_ids.workcenter_id, self.service_workcenter)
        self.assertFalse(duplicate.line_ids.product_id)
        self.assertFalse(duplicate.line_ids.bom_id)

    def test_06_blocks_incomplete_estimate(self):
        estimate = self._create_estimate()
        estimate.line_ids.bom_line_ids.unlink()
        with self.assertRaises(UserError):
            estimate.action_create_sale_order()
        self.assertFalse(estimate.line_ids.product_id)

    def test_08_form_fills_costs_from_material(self):
        env = self.env(user=self.salesman, context={'allowed_company_ids': self.service_company.ids})
        form = Form(env['sale.estimate'])
        form.partner_id = self.customer
        with form.line_ids.new() as line:
            line.name = 'Ghe may do'
            line.extra_cost = 10000
            line.price_option = '2'
            with line.bom_line_ids.new() as bom_line:
                bom_line.product_id = self.fabric
                bom_line.product_qty = 2
            # Dòng mới có sẵn khu vực chọn được (khu vực KHAC không có ở công ty sản xuất nên không có)
            self.assertEqual(len(line.operation_ids), 1)
            with line.operation_ids.edit(0) as operation:
                self.assertEqual(operation.workcenter_id, self.service_workcenter)
                operation.time_cycle_manual = 10
                self.assertEqual(operation.name, 'May TM')
                self.assertEqual(operation.costs_hour, 60000)
        estimate = form.save()
        self.assertEqual(estimate.line_ids.bom_line_ids.product_uom_id, self.fabric.uom_id)
        self.assertEqual(estimate.line_ids.cost_unit, 220000)
        # (220.000 x 2) x 1,25 x 2,2 = 1.210.000 -> 1.200.000
        self.assertEqual(estimate.line_ids.price_unit, 1200000)

    def test_10_salesman_only_picks_linked_workcenters(self):
        env = self.env(user=self.salesman, context={'allowed_company_ids': self.service_company.ids})
        Workcenter = env['mrp.workcenter'].with_context(sale_estimate_workcenter=True)
        results = Workcenter.web_name_search('', {'display_name': {}, 'costs_hour': {}})
        self.assertEqual([result['id'] for result in results], self.service_workcenter.ids)
        self.assertEqual(set(results[0]), {'id', 'display_name', '__formatted_display_name'})
        with self.assertRaises(AccessError):
            env['mrp.workcenter'].web_name_search('', {'display_name': {}})

    def test_09_salesman_confirms_order(self):
        # tiny_sale_purchase xác nhận PO bằng quyền người dùng nên cần nhóm Mua hàng
        self.salesman.group_ids |= self.env.ref('purchase.group_purchase_user')
        estimate = self._create_estimate()
        estimate.action_create_sale_order()
        estimate.sale_order_id.action_confirm()
        self.assertEqual(estimate.sale_order_id.state, 'sale')

    def test_11_blocks_workcenter_without_same_code(self):
        estimate = self._create_estimate()
        estimate.line_ids.operation_ids.workcenter_id = self.other_workcenter
        self.assertEqual(estimate.line_ids.operation_ids.costs_hour, 0)
        with self.assertRaises(UserError):
            estimate.action_create_sale_order()
        self.assertFalse(estimate.line_ids.product_id)

    def test_13_operation_settings_go_to_bom(self):
        estimate = self._create_estimate()
        estimate.line_ids.operation_ids.write({'cost_mode': 'estimated', 'time_mode': 'auto', 'time_mode_batch': 5})
        estimate.action_create_sale_order()
        operation = estimate.sudo().line_ids.bom_id.operation_ids
        self.assertEqual(operation.cost_mode, 'estimated')
        self.assertEqual(operation.time_mode, 'auto')
        self.assertEqual(operation.time_mode_batch, 5)
        self.assertEqual(operation.time_cycle_manual, 30)

    def test_14_employee_cost_matches_bom(self):
        self.workcenter.employee_costs_hour = 120000
        estimate = self._create_estimate()
        operation = estimate.line_ids.operation_ids
        operation.employee_ratio = 2
        self.assertEqual(operation.employee_costs_hour, 120000)
        self.assertEqual(operation.subtotal, 150000)
        estimate.action_create_sale_order()
        bom_operation = estimate.sudo().line_ids.bom_id.operation_ids
        self.assertEqual(bom_operation.employee_ratio, 2)
        self.assertEqual(bom_operation.cost, 150000)

    def test_15_instructions_become_quality_points(self):
        estimate = self._create_estimate()
        estimate.line_ids.operation_ids.instruction_ids = [Command.create({
            'title': 'Kiem tra duong may', 'test_type': 'picture', 'note': '<p>Chup mat sau</p>'})]
        estimate.action_create_sale_order()
        line = estimate.sudo().line_ids
        point = line.bom_id.operation_ids.quality_point_ids
        self.assertEqual(point.title, 'Kiem tra duong may')
        self.assertEqual(point.test_type, 'picture')
        self.assertEqual(point.product_ids, line.product_id)
        self.assertEqual(point.company_id, self.mrp_company)
        duplicate = estimate.copy()
        self.assertEqual(duplicate.line_ids.operation_ids.instruction_ids.title, 'Kiem tra duong may')

    def test_12_code_unique_in_company(self):
        with self.assertRaises(ValidationError):
            self.env['mrp.workcenter'].with_company(self.mrp_company).create({
                'name': 'May 2', 'code': 'MAY', 'company_id': self.mrp_company.id})

    def test_07_requires_route_configuration(self):
        estimate = self._create_estimate()
        self.service_company.estimate_route_ids = False
        with self.assertRaises(UserError):
            estimate.action_create_sale_order()

    # ---------------- Tính giá theo sheet bespoke ----------------

    def _create_price_estimate(self, user=None, **line_vals):
        """Phiếu tính giá, giá vốn 2.432.000 như dòng mẫu trong file Excel."""
        env = self.env(user=user or self.salesman, context={'allowed_company_ids': self.service_company.ids})
        return env['sale.estimate'].with_company(self.service_company).with_context(
            default_estimate_type='price').create({
                'line_ids': [Command.create({'name': 'Dam may do', 'extra_cost': 2432000, **line_vals})],
            })

    def test_20_price_levels_match_excel(self):
        line = self._create_price_estimate().line_ids
        self.assertEqual(line.cost_unit, 2432000)
        self.assertAlmostEqual(line.studio_cost, 2432000)
        self.assertAlmostEqual(line.profit_lv1, 972800)
        self.assertAlmostEqual(line.profit_lv2, 1216000)
        self.assertAlmostEqual(line.total_cost_lv1, 5836800)
        self.assertAlmostEqual(line.total_cost_lv2, 6080000)
        self.assertAlmostEqual(line.price_lv1_1, 10506240)
        self.assertAlmostEqual(line.price_lv1_2, 12840960)
        self.assertAlmostEqual(line.price_lv1_3, 14592000)
        self.assertAlmostEqual(line.price_lv2_1, 11552000)
        self.assertAlmostEqual(line.price_lv2_2, 13376000)
        self.assertAlmostEqual(line.price_lv2_3, 15200000)
        self.assertEqual(line.packaging_total, 87500)

    def test_21_final_price_rounding_and_manual(self):
        line = self._create_price_estimate().line_ids
        self.assertEqual((line.price_level, line.price_option), ('lv2', '1'))
        self.assertAlmostEqual(line.suggested_price, 11552000)
        self.assertEqual(line.price_unit, 11600000)
        self.assertFalse(line.price_manual)
        self.assertEqual(line.price_factor_label, '× 1,9')
        line.price_option = '2'
        self.assertEqual(line.price_unit, 13400000)
        line.write({'price_level': 'lv1', 'price_option': '1'})
        self.assertEqual(line.price_unit, 10500000)  # Excel: 10.506 -> 10.500
        line.price_unit = 12000000
        self.assertTrue(line.price_manual)
        # Bao bì không cộng vào giá
        line.packaging_box = 100000
        self.assertEqual(line.price_unit, 12000000)

        estimate = self._create_estimate()
        estimate.line_ids.price_unit = 2500000
        self.assertTrue(estimate.line_ids.price_manual)
        estimate.action_create_sale_order()
        self.assertEqual(estimate.sale_order_id.sudo().order_line.price_unit, 2500000)
        self.assertEqual(estimate.line_ids.product_id.sudo().list_price, 2500000)

    def test_22_channel_prices(self):
        line = self._create_price_estimate().line_ids
        self.assertAlmostEqual(line.showroom_markup_1, 8120000)
        self.assertAlmostEqual(line.showroom_markup_2, 20300000)
        self.assertAlmostEqual(line.showroom_markup_3, 17024000)
        self.assertEqual(line.rrp_showroom, 20300000)
        self.assertAlmostEqual(line.wsp_price, 8120000)
        self.assertAlmostEqual(line.ecom_price, 10150000)
        self.assertAlmostEqual(line.wsp2_price, 8526000)
        self.assertAlmostEqual(line.profit_ecom_pct, (10150000 - 5836800) / 5836800, places=6)
        self.assertAlmostEqual(line.profit_wsp_pct, (8120000 - 5836800) / 5836800, places=6)
        self.assertAlmostEqual(line.compare_vn_pct, 0.75, places=6)
        # RRP showroom sửa tay được, giá kênh tính theo giá sửa
        line.rrp_showroom = 18450000
        self.assertAlmostEqual(line.ecom_price, 9225000)
        # Chia cho 0 trả 0
        zero = self._create_price_estimate(extra_cost=0).line_ids
        self.assertEqual((zero.profit_ecom_pct, zero.profit_wsp_pct, zero.compare_vn_pct), (0, 0, 0))

    def test_23_usd_uses_odoo_rate(self):
        self.usd.sudo().rate_ids.unlink()
        line = self._create_price_estimate().line_ids
        self.assertEqual(line.usd_currency_id, self.usd)
        self.assertEqual(line.price_unit_usd, 0)  # chưa có tỷ giá thì không quy đổi, không báo lỗi

        self.env['res.currency.rate'].create({
            'currency_id': self.usd.id,
            'company_id': self.service_company.id,
            'name': line.estimate_id.date_estimate,
            'rate': 1 / 25000,
        })
        estimate = self._create_price_estimate()
        line = estimate.line_ids
        self.assertAlmostEqual(line.price_unit_usd, 464, places=2)  # 11.600.000 / 25.000
        self.assertAlmostEqual(line.rrp_showroom_usd, 812, places=2)
        self.assertAlmostEqual(estimate.amount_total_usd, 464, places=2)

    def test_24_pricing_uses_material_and_operation_tabs(self):
        estimate = self._create_estimate()
        line = estimate.line_ids
        self.assertEqual(line.material_cost, 300000)
        self.assertEqual(line.operation_cost, 30000)
        self.assertEqual(line.cost_unit, 380000)
        self.assertAlmostEqual(line.studio_cost, 380000)
        self.assertAlmostEqual(line.total_cost_lv2, 950000)
        line.bom_line_ids.product_qty = 4
        self.assertEqual(line.cost_unit, 480000)
        self.assertAlmostEqual(line.total_cost_lv2, 1200000)

    def test_25_price_estimate_flow(self):
        estimate = self._create_price_estimate()
        self.assertEqual(estimate.estimate_type, 'price')
        self.assertFalse(estimate.partner_id)
        self.assertEqual(estimate.line_ids.estimate_type, 'price')
        with self.assertRaises(UserError):
            estimate.action_create_sale_order()
        estimate.line_ids.write({
            'bom_line_ids': [Command.create({'product_id': self.fabric.id, 'product_qty': 2})],
            'operation_ids': [Command.create({'workcenter_id': self.service_workcenter.id, 'time_cycle_manual': 20})],
        })
        estimate.line_ids.price_unit = 12345000
        estimate.action_done()
        self.assertEqual(estimate.state, 'done')
        with self.assertRaises(UserError):
            estimate.action_convert_to_order()  # chưa có khách

        estimate.partner_id = self.customer
        action = estimate.action_convert_to_order()
        order_estimate = estimate.browse(action['res_id'])
        self.assertNotEqual(order_estimate, estimate)
        self.assertEqual(order_estimate.estimate_type, 'order')
        self.assertEqual(order_estimate.state, 'draft')
        self.assertEqual(order_estimate.partner_id, self.customer)
        self.assertEqual(order_estimate.line_ids.bom_line_ids.product_id, self.fabric)
        self.assertEqual(order_estimate.line_ids.operation_ids.workcenter_id, self.service_workcenter)
        self.assertEqual(order_estimate.line_ids.price_unit, 12345000)
        self.assertEqual(estimate.state, 'done')  # phiếu gốc giữ nguyên

        estimate.action_reset_draft()
        self.assertEqual(estimate.state, 'draft')
        order_estimate.action_create_sale_order()
        self.assertEqual(order_estimate.state, 'ordered')
        with self.assertRaises(UserError):
            order_estimate.estimate_type = 'price'


    def test_26_order_estimate_requires_partner(self):
        env = self.env(user=self.salesman, context={'allowed_company_ids': self.service_company.ids})
        with self.assertRaises(ValidationError):
            env['sale.estimate'].with_company(self.service_company).create({
                'line_ids': [Command.create({'name': 'Sofa'})]})
        with self.assertRaises(UserError):
            self._create_estimate().action_done()

    def test_27_salesman_uses_pricing_menu(self):
        estimate = self._create_price_estimate(user=self.salesman)
        line = estimate.line_ids
        line.write({'studio_rate': 0.5, 'price_option': '3'})
        self.assertAlmostEqual(line.total_cost_lv2, 3648000 * 1.25)
        Line = self.env['sale.estimate.line'].with_user(self.salesman).with_context(
            allowed_company_ids=self.service_company.ids)
        lines = Line.search([('estimate_type', '=', 'price'), ('state', 'in', ('draft', 'done'))])
        self.assertIn(line, lines)
        lines.read(['cost_unit', 'total_cost_lv2', 'price_unit', 'price_unit_usd', 'profit_ecom_pct'])
        Line._read_group([('estimate_type', '=', 'price')], ['estimate_id'], ['price_unit:sum'])
        action = line.with_user(self.salesman).action_open_estimate()
        self.assertEqual((action['res_model'], action['res_id']), ('sale.estimate', estimate.id))
        menus = self.env['ir.ui.menu'].with_user(self.salesman)._visible_menu_ids()
        for xmlid in ('menu_sale_estimate_price', 'menu_sale_estimate_line_pricing', 'menu_sale_estimate'):
            self.assertIn(self.env.ref('tiny_sale_mrp.%s' % xmlid).id, menus)
        estimate.with_user(self.salesman).action_done()
        self.assertEqual(estimate.state, 'done')

    def test_28_workcenter_estimate_time_fills_duration(self):
        self.workcenter.estimate_time = 45
        env = self.env(user=self.salesman, context={'allowed_company_ids': self.service_company.ids})
        form = Form(env['sale.estimate'].with_context(default_estimate_type='price'))
        with form.line_ids.new() as line:
            line.name = 'Ao may do'
            # Hoạt động mặc định cũng lấy thời lượng của khu vực cùng mã ở công ty sản xuất
            with line.operation_ids.edit(0) as operation:
                self.assertEqual(operation.time_cycle_manual, 45)
            line.operation_ids.remove(0)
            with line.operation_ids.new() as operation:
                self.assertEqual(operation.time_cycle_manual, 60)
                operation.workcenter_id = self.service_workcenter
                # Lấy theo khu vực cùng mã ở công ty sản xuất
                self.assertEqual(operation.time_cycle_manual, 45)
            with line.operation_ids.new() as operation:
                operation.workcenter_id = self.other_workcenter
                self.assertEqual(operation.time_cycle_manual, 60)  # khu vực không khai báo thì giữ nguyên
        estimate = form.save()
        self.assertEqual(estimate.line_ids.operation_ids.mapped('time_cycle_manual'), [45, 60])

        # Hoạt động của BOM (tiny_mrp)
        self.workcenter.estimate_time = 25
        bom = self.env['mrp.bom'].with_company(self.mrp_company).create({
            'product_tmpl_id': self.fabric.product_tmpl_id.id, 'company_id': self.mrp_company.id})
        operation_form = Form(self.env['mrp.routing.workcenter'].with_company(self.mrp_company).with_context(
            default_bom_id=bom.id))
        operation_form.name = 'May'
        operation_form.workcenter_id = self.workcenter
        self.assertEqual(operation_form.time_cycle_manual, 25)
        self.assertEqual(operation_form.save().time_cycle_manual, 25)

    def test_29_multi_company_rules(self):
        """Người dùng chỉ thuộc công ty khác không đọc được phiếu dự toán và dữ liệu con."""
        estimate = self._create_estimate()
        line = estimate.line_ids
        line.operation_ids.instruction_ids = [Command.create({'title': 'Kiem tra duong may'})]
        other_company = self.env['res.company'].create({'name': 'Tiny Cong Ty Khac'})
        other_user = new_test_user(
            self.env, login='estimate_sales_other', groups='sales_team.group_sale_salesman',
            company_id=other_company.id, company_ids=[Command.set(other_company.ids)])
        other_env = self.env(user=other_user, context={'allowed_company_ids': other_company.ids})
        records = {
            'sale.estimate': estimate,
            'sale.estimate.line': line,
            'sale.estimate.operation': line.operation_ids,
            'sale.estimate.instruction': line.operation_ids.instruction_ids,
            'sale.estimate.bom.line': line.bom_line_ids,
        }
        for model, record in records.items():
            self.assertTrue(record, model)
            self.assertFalse(other_env[model].search([('id', 'in', record.ids)]), model)
            with self.assertRaises(AccessError, msg=model):
                other_env[model].browse(record.ids).read(['display_name'])
            # Người dùng cùng công ty vẫn đọc được
            sales_env = self.env(user=self.salesman, context={'allowed_company_ids': self.service_company.ids})
            self.assertEqual(sales_env[model].search([('id', 'in', record.ids)]), record.with_env(sales_env), model)
