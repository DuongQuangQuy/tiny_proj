from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestSaleEstimate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.service_company = env['res.company'].create({'name': 'Tiny Thuong Mai', 'is_service': True})
        cls.mrp_company = env['res.company'].create({'name': 'Tiny San Xuat', 'is_mrp': True})
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
                'code_fabric': 'V01',
                'note': 'Theo yeu cau',
                'extra_cost': 50000,
                'markup_factor': 1.2,
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
        self.assertEqual(line.price_unit, 456000)
        self.assertEqual(estimate.amount_total, 912000)
        self.assertEqual(estimate.amount_margin, 152000)

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
        self.assertEqual(line.product_id.code_fabric, 'V01')
        self.assertEqual(line.product_id.seller_ids.partner_id, self.mrp_company.partner_id)
        self.assertEqual(line.product_id.seller_ids.price, 380000)
        self.assertEqual(line.product_id.with_company(self.mrp_company).standard_price, 380000)
        order_line = estimate.sale_order_id.sudo().order_line
        self.assertEqual(order_line.price_unit, 456000)
        self.assertEqual(order_line.product_uom_qty, 2)
        self.assertEqual(order_line.product_size, '2m x 1m')
        self.assertEqual(order_line.code_fabric, 'V01')

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
            line.markup_factor = 1.5
            with line.bom_line_ids.new() as bom_line:
                bom_line.product_id = self.fabric
                bom_line.product_qty = 2
            with line.operation_ids.new() as operation:
                operation.workcenter_id = self.service_workcenter
                operation.time_cycle_manual = 10
                self.assertEqual(operation.name, 'May TM')
                self.assertEqual(operation.costs_hour, 60000)
        estimate = form.save()
        self.assertEqual(estimate.line_ids.bom_line_ids.product_uom_id, self.fabric.uom_id)
        self.assertEqual(estimate.line_ids.cost_unit, 220000)
        self.assertEqual(estimate.line_ids.price_unit, 330000)

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
