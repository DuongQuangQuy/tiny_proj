from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMrpReviewFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Quản lý xưởng: user nội bộ, quyền Sản xuất > Người dùng, có trong Quản lý duyệt của khu vực
        cls.reviewer = cls.env['res.users'].create({
            'name': 'Quản lý xưởng test', 'login': 'tiny_reviewer_test',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.env.ref('mrp.group_mrp_user').id])],
        })
        cls.outsider = cls.env['res.users'].create({
            'name': 'Thợ test', 'login': 'tiny_worker_test',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.env.ref('mrp.group_mrp_user').id])],
        })
        Workcenter = cls.env['mrp.workcenter']
        cls.wc_cut = Workcenter.create({'name': 'Cắt test', 'code': 'RV_CUT', 'review_policy': 'none'})
        cls.wc_sew = Workcenter.create({
            'name': 'May test', 'code': 'RV_SEW', 'review_policy': 'optional', 'default_review_mode': 'before',
            'user_review_ids': [(6, 0, cls.reviewer.ids)]})
        cls.wc_paint = Workcenter.create({
            'name': 'Vẽ test', 'code': 'RV_PAINT', 'review_policy': 'required',
            'user_review_ids': [(6, 0, cls.reviewer.ids)]})
        cls.wc_finish = Workcenter.create({
            'name': 'Finishing test', 'code': 'RV_FIN', 'review_policy': 'required',
            'user_review_ids': [(6, 0, cls.reviewer.ids)]})
        cls.product = cls.env['product.product'].create({'name': 'Túi test duyệt', 'is_storable': True})
        cls.component = cls.env['product.product'].create({'name': 'Vải test duyệt', 'is_storable': True})
        warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1)
        cls.env['stock.quant']._update_available_quantity(cls.component, warehouse.lot_stock_id, 100)
        cls.defect = cls.env.ref('tiny_approvals_mrp.mrp_reason_defect_pattern')

    # ------------------------------------------------------------------
    def _create_production(self, operations):
        """MO đã xác nhận, kho đã xác nhận. operations = [(tên, khu vực), ...]."""
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
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1,
            'bom_id': bom.id,
        })
        production.action_confirm()
        production.action_confirm_stock()
        return production

    def _full_production(self):
        return self._create_production([
            ('Cắt', self.wc_cut), ('May', self.wc_sew), ('Vẽ', self.wc_paint), ('Finishing', self.wc_finish)])

    def _wo(self, production, name):
        return production.workorder_ids.filtered(lambda wo: wo.name == name)

    def _log_time(self, workorder, minutes=10):
        """Ghi một phiên giờ đã đóng (không dùng sleep)."""
        end = fields.Datetime.now()
        vals = workorder._prepare_timeline_vals(0, end - timedelta(minutes=minutes), end)
        return self.env['mrp.workcenter.productivity'].create(vals)

    def _run(self, workorder, minutes=10):
        workorder.button_start(bypass=True)
        self._log_time(workorder, minutes)
        workorder.button_finish()
        self.assertEqual(workorder.state, 'done')

    def _pass_last_review(self, workorder):
        review = workorder.last_review_id.with_user(self.reviewer)
        review.action_start_review()
        review.action_pass()
        return review

    def _mark_done(self, production):
        production.button_mark_done()
        self.assertEqual(production.state, 'done')

    # ------------------------------------------------------------------
    def test_01_no_review_config(self):
        """Không cấu hình điểm duyệt: chạy như cũ, không sinh yêu cầu duyệt, đánh dấu hoàn thành được."""
        wc_other = self.env['mrp.workcenter'].create({'name': 'Đính kết test', 'code': 'RV_ATTACH'})
        production = self._create_production([('Cắt', self.wc_cut), ('Đính kết', wc_other)])
        self.assertEqual(set(production.workorder_ids.mapped('review_mode')), {'none'})
        for workorder in production.workorder_ids:
            self.assertFalse(workorder._get_flow_block_reason())
            self._run(workorder)
        self.assertFalse(production.review_ids)
        self.assertEqual(set(production.workorder_ids.mapped('review_state')), {'no'})
        self.assertFalse(production.has_open_review_or_rework)
        self.assertGreater(production.duration_new, 0)
        self.assertEqual(production.duration_rework, 0)
        self._mark_done(production)

    def test_02_required_review(self):
        production = self._full_production()
        cut, sew, paint, finish = (self._wo(production, n) for n in ('Cắt', 'May', 'Vẽ', 'Finishing'))
        self.assertEqual(paint.review_policy, 'required')
        self.assertEqual(paint.review_mode, 'before')
        self.assertEqual(sew.review_mode, 'before')
        self.assertEqual(paint.user_review_ids, self.reviewer)

        self._run(cut)
        self.assertFalse(cut.review_ids)
        self._run(sew)
        self.assertEqual(sew.review_state, 'waiting')
        with self.assertRaisesRegex(UserError, 'Công đoạn May chưa được duyệt đạt'):
            paint.button_start(bypass=True)
        self._pass_last_review(sew)

        self._run(paint)
        review = paint.last_review_id.with_user(self.reviewer)
        self.assertEqual(review.round_no, 1)
        self.assertEqual(review.state, 'waiting')
        self.assertEqual(review.mode, 'before')
        self.assertTrue(review.activity_ids, 'Phải tạo hoạt động Duyệt công đoạn cho quản lý duyệt')
        with self.assertRaisesRegex(UserError, 'Công đoạn Vẽ chưa được duyệt đạt'):
            finish.button_start(bypass=True)
        with self.assertRaisesRegex(UserError, 'Nhận duyệt'):
            review.action_pass()
        with self.assertRaisesRegex(UserError, 'không phải quản lý duyệt'):
            review.with_user(self.outsider).action_start_review()

        review.action_start_review()
        self.assertEqual(review.state, 'reviewing')
        self.assertEqual(review.reviewer_id, self.reviewer)
        review.action_pause_review()
        self.assertEqual(review.state, 'paused')
        review.action_start_review()
        self.assertEqual(review.state, 'reviewing')
        review.action_pass()
        self.assertEqual(review.state, 'passed')
        self.assertTrue(review.date_done)
        self.assertGreaterEqual(review.review_duration, 0)
        self.assertFalse(review.activity_ids)
        self.assertEqual(paint.review_state, 'passed')

        self.assertFalse(finish._get_flow_block_reason())
        finish.button_start(bypass=True)
        self.assertEqual(finish.state, 'progress')

    def test_03_fail_in_place_rework_time(self):
        production = self._full_production()
        cut, sew, paint, finish = (self._wo(production, n) for n in ('Cắt', 'May', 'Vẽ', 'Finishing'))
        self._run(cut)
        self._run(sew)
        self._pass_last_review(sew)
        self._run(paint, minutes=30)
        duration_new = paint.duration_new
        self.assertEqual(paint.duration_rework, 0)

        review = paint.last_review_id.with_user(self.reviewer)
        review.action_start_review()
        review.action_fail(defect_reason_ids=self.defect, note='Sai màu', return_workorder_id=paint)
        self.assertEqual(review.state, 'failed')
        self.assertTrue(review.return_id)
        self.assertEqual(paint.state, 'ready')
        self.assertEqual(paint.rework_return_id, review.return_id)
        self.assertEqual(paint.review_state, 'failed')
        self.assertEqual(production.state, 'progress')
        with self.assertRaisesRegex(UserError, 'Công đoạn Vẽ đang được chỉnh lại'):
            finish.button_start(bypass=True)

        # Phiên giờ khi đang sửa là giờ sửa, kể cả sau Tạm dừng -> Tiếp tục
        paint.button_start(bypass=True)
        time_1 = self._log_time(paint, 5)
        self.assertEqual(time_1.work_type, 'rework')
        self.assertEqual(time_1.return_id, review.return_id)
        paint.button_pending()
        self.assertTrue(paint.rework_return_id, 'Tạm dừng không tắt cờ đang sửa')
        paint.button_start(bypass=True)
        time_2 = self._log_time(paint, 7)
        self.assertEqual(time_2.work_type, 'rework')
        self.assertEqual(time_2.return_id, review.return_id)
        paint.button_finish()

        ret = review.return_id
        self.assertEqual(ret.state, 'done')
        self.assertTrue(ret.date_resolved)
        self.assertFalse(paint.rework_return_id)
        self.assertEqual(paint.rework_count, 1)
        self.assertAlmostEqual(ret.rework_duration, 12, places=1)
        self.assertAlmostEqual(paint.duration_rework, 12, places=1)
        self.assertAlmostEqual(paint.duration_new, duration_new, places=2)
        self.assertEqual(production.rework_count, 1)
        self.assertGreater(production.duration_rework, 0)
        review_2 = paint.last_review_id
        self.assertEqual(review_2.round_no, 2)
        self.assertEqual(review_2.state, 'waiting')
        self._pass_last_review(paint)
        self.assertFalse(finish._get_flow_block_reason())

    def test_04_return_to_previous_operation(self):
        production = self._full_production()
        cut, sew, paint, finish = (self._wo(production, n) for n in ('Cắt', 'May', 'Vẽ', 'Finishing'))
        sew.review_mode = 'after'
        self._run(cut)
        self._run(sew)
        self._pass_last_review(sew)
        self._run(paint)
        self._pass_last_review(paint)
        self._run(finish)

        review = finish.last_review_id.with_user(self.reviewer)
        review.action_start_review()
        review.action_fail(defect_reason_ids=self.defect, note='Đường may lệch', return_workorder_id=sew,
                           assign_user_ids=self.reviewer)
        self.assertEqual(sew.state, 'ready')
        self.assertTrue(sew.rework_return_id)
        self.assertEqual(sew.rework_return_id.from_workorder_id, finish)
        self.assertEqual(sew.user_mrp_ids, self.reviewer)
        # Finishing đã xong nên được mở lại với lượt chỉnh riêng, chờ May chỉnh xong
        self.assertEqual(finish.state, 'ready')
        self.assertTrue(finish.rework_return_id)
        self.assertEqual(paint.state, 'done', 'Công đoạn ở giữa giữ nguyên')
        with self.assertRaisesRegex(UserError, 'Công đoạn May đang được chỉnh lại'):
            finish.button_start(bypass=True)
        self.assertIn('bị trả về', production.message_ids[:1].body)

        sew.button_start(bypass=True)
        self.assertEqual(self._log_time(sew).work_type, 'rework')
        sew.button_finish()
        self.assertFalse(sew.rework_return_id)
        self.assertFalse(sew.user_mrp_ids, 'Trả lại người thực hiện cũ của khu vực (trống)')
        self.assertEqual(sew.last_review_id.round_no, 2)
        self.assertEqual(sew.last_review_id.mode, 'after')

        # May kiểm sau: Finishing làm tiếp được, giờ làm lại là giờ sửa
        self.assertFalse(finish._get_flow_block_reason())
        finish.button_start(bypass=True)
        self.assertEqual(self._log_time(finish).work_type, 'rework')
        finish.button_finish()
        self.assertEqual(finish.last_review_id.round_no, 2)

    def test_05_review_after_blocks_mark_done(self):
        production = self._full_production()
        cut, sew, paint, finish = (self._wo(production, n) for n in ('Cắt', 'May', 'Vẽ', 'Finishing'))
        sew.review_mode = 'after'
        self._run(cut)
        self._run(sew)
        self.assertEqual(sew.review_state, 'waiting')
        self.assertFalse(paint._get_flow_block_reason())
        self._run(paint)
        self._pass_last_review(paint)
        self._run(finish)
        self._pass_last_review(finish)
        with self.assertRaisesRegex(UserError, 'còn yêu cầu duyệt'):
            production.button_mark_done()
        self._pass_last_review(sew)
        self.assertFalse(production.has_open_review_or_rework)
        self._mark_done(production)

    def test_06_change_review_mode(self):
        production = self._full_production()
        sew, paint = self._wo(production, 'May'), self._wo(production, 'Vẽ')
        with self.assertRaisesRegex(UserError, 'bắt buộc duyệt'):
            paint.review_mode = 'after'
        self.assertTrue(sew.can_edit_review_mode)
        sew.review_mode = 'none'
        self.assertEqual(sew.review_mode_user_id, self.env.user)
        self.assertTrue(sew.review_mode_date)
        self._run(self._wo(production, 'Cắt'))
        self._run(sew)
        self.assertFalse(sew.review_ids, 'Không yêu cầu kiểm thì không sinh yêu cầu duyệt')
        with self.assertRaisesRegex(UserError, 'đã kết thúc'):
            sew.review_mode = 'before'

    def test_07_cancel_production_cancels_reviews(self):
        production = self._full_production()
        self._run(self._wo(production, 'Cắt'))
        sew = self._wo(production, 'May')
        self._run(sew)
        review = sew.last_review_id
        self.assertEqual(review.state, 'waiting')
        production.action_cancel()
        self.assertEqual(review.state, 'cancel')
