from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError
from odoo.addons.tiny_mrp.controller.main import (
    _make_fmt_dt, _STATE_LABEL, _STATE_COLOR, _PRODUCTION_STATE_LABEL, _PRODUCTION_STATE_COLOR,
)

from .main import MrpApprovalsPortal

OPEN_REVIEW_STATES = ('waiting', 'reviewing', 'paused')

_REVIEW_STATE_LABEL = {
    'no': 'Không duyệt',
    'waiting': 'Chờ quản lý duyệt',
    'reviewing': 'Đang duyệt',
    'paused': 'Tạm dừng duyệt',
    'passed': 'Đạt',
    'failed': 'Chưa đạt',
    'cancel': 'Đã hủy',
}

_REVIEW_STATE_COLOR = {
    'no': 'bg-light text-dark border',
    'waiting': 'bg-warning text-dark',
    'reviewing': 'bg-info text-dark',
    'paused': 'bg-secondary',
    'passed': 'bg-success',
    'failed': 'bg-danger',
    'cancel': 'bg-secondary',
}

_REVIEW_MODE_LABEL = {
    'before': 'Kiểm trước',
    'after': 'Kiểm sau',
    'none': 'Không yêu cầu kiểm',
}


def _fmt_minutes(minutes):
    minutes = int(round(minutes or 0))
    return '%02d:%02d' % (minutes // 60, minutes % 60)


class MrpReviewPortal(MrpApprovalsPortal):

    # ------------------------------------------------------------------
    # Tiện ích chung
    # ------------------------------------------------------------------
    def _review_common_values(self):
        return {
            'review_state_label': _REVIEW_STATE_LABEL,
            'review_state_color': _REVIEW_STATE_COLOR,
            'review_mode_label': _REVIEW_MODE_LABEL,
            'fmt_minutes': _fmt_minutes,
        }

    def _get_review_domain(self, user):
        domain = [('state', 'in', OPEN_REVIEW_STATES)]
        if not user.has_group('mrp.group_mrp_manager'):
            domain.append(('workorder_id.user_review_ids', 'in', user.id))
        return domain

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'review_count' in counters:
            user = request.env.user
            values['review_count'] = request.env['mrp.workorder.review'].sudo().search_count(
                self._get_review_domain(user))
        return values

    # ------------------------------------------------------------------
    # Lệnh công việc của thợ
    # ------------------------------------------------------------------
    @http.route('/my/workorders', auth='user', website=True, type='http')
    def portal_workorders(self, **kw):
        response = super().portal_workorders(**kw)
        qcontext = getattr(response, 'qcontext', None)
        if qcontext is None or 'workorders' not in qcontext:
            return response
        user = request.env.user
        # Công đoạn đang được chỉnh lại luôn hiện với người được giao
        reworks = request.env['mrp.workorder'].sudo().search([
            ('user_mrp_ids', 'in', user.id),
            ('state', 'not in', ('done', 'cancel')),
            ('rework_return_id', '!=', False),
        ])
        workorders = qcontext['workorders']
        workorders = workorders + (reworks - workorders)
        qcontext.update({
            'workorders': workorders,
            'flow_block_reasons': {
                wo.id: wo._get_flow_block_reason() for wo in workorders if wo.state != 'progress'},
            **self._review_common_values(),
        })
        return response

    def _workorder_detail_values(self, workorder, user, **extra):
        vals = super()._workorder_detail_values(workorder, user, **extra)
        vals.update({
            # Portal tạm dừng chỉ lấy lý do loại Tạm dừng
            'mrp_reasons': request.env['mrp.reason'].sudo().search([('reason_type', '=', 'pause')]),
            'rework': workorder.rework_return_id,
            'review_history': workorder.review_ids.sorted(lambda r: (r.round_no, r.id), reverse=True),
            **self._review_common_values(),
        })
        return vals

    # ------------------------------------------------------------------
    # Người duyệt
    # ------------------------------------------------------------------
    def _get_review(self, review_id):
        user = request.env.user
        review = request.env['mrp.workorder.review'].sudo().browse(review_id)
        if not review.exists() or not review.workorder_id._tiny_is_reviewer(user):
            return None
        return review

    def _review_detail_values(self, review, user, **extra):
        workorder = review.workorder_id
        production = review.production_id
        targets = (workorder | workorder._tiny_get_all_previous_workorders()).sorted(
            lambda wo: wo._tiny_sort_key())
        assignable_users = (request.env['mrp.workcenter'].sudo().search([]).user_mrp_ids
                            | production.workorder_ids.user_mrp_ids).sorted('name')
        vals = {
            'review': review,
            'workorder': workorder,
            'production': production,
            'product_image_src': self._get_product_image_src(production.product_id),
            'fmt_dt': _make_fmt_dt(request.env),
            'page_name': 'review',
            'defect_reasons': request.env['mrp.reason'].sudo().search([('reason_type', '=', 'defect')]),
            'return_targets': targets,
            'assignable_users': assignable_users,
            'previous_reviews': (workorder.review_ids - review).sorted(lambda r: (r.round_no, r.id), reverse=True),
            'state_label': _STATE_LABEL,
            'state_color': _STATE_COLOR,
            **self._review_common_values(),
        }
        vals.update(extra)
        return vals

    @http.route('/my/reviews', auth='user', website=True, type='http')
    def portal_reviews(self, **kw):
        user = request.env.user
        reviews = request.env['mrp.workorder.review'].sudo().search(
            self._get_review_domain(user), order='date_request asc, id asc')
        return request.render('tiny_approvals_mrp.portal_my_reviews', {
            'reviews': reviews,
            'fmt_dt': _make_fmt_dt(request.env),
            'page_name': 'review',
            **self._review_common_values(),
        })

    @http.route('/my/reviews/<int:review_id>', auth='user', website=True, type='http')
    def portal_review_detail(self, review_id, **kw):
        user = request.env.user
        review = self._get_review(review_id)
        if not review:
            return request.not_found()
        return request.render('tiny_approvals_mrp.portal_review_detail', self._review_detail_values(review, user))

    @http.route('/my/reviews/<int:review_id>/action', auth='user', website=True, type='http', methods=['POST'])
    def portal_review_action(self, review_id, action=None, **kw):
        user = request.env.user
        review = self._get_review(review_id)
        if not review:
            return request.not_found()

        error = None
        try:
              with request.env.cr.savepoint():
                  self._do_review_action(review, action, **kw)
        except UserError as e:
            error = e.args[0] if e.args else str(e)
        except (ValueError, TypeError):
            error = _('Dữ liệu gửi lên không hợp lệ.')

        if error:
            return request.render('tiny_approvals_mrp.portal_review_detail',
                                  self._review_detail_values(review, user, error=error))
        return request.redirect('/my/reviews/%d' % review_id)

    def _do_review_action(self, review, action, **kw):
        if action in ('start', 'resume'):
            review.action_start_review()
        elif action == 'pause':
            review.action_pause_review()
        elif action == 'pass':
            review.action_pass()
        elif action == 'fail':
            form = request.httprequest.form
            reason_ids = [int(x) for x in form.getlist('defect_reason_ids') if x]
            reasons = request.env['mrp.reason'].sudo().browse(reason_ids).exists().filtered(
                lambda r: r.reason_type == 'defect')
            note = (kw.get('note') or '').strip()
            if not reasons and not note:
                raise UserError(_('Vui lòng chọn lỗi hoặc ghi chú khi đánh giá Chưa đạt.'))
            workorder = review.workorder_id
            allowed = workorder | workorder._tiny_get_all_previous_workorders()
            target_id = int(kw.get('return_workorder_id') or workorder.id)
            target = allowed.filtered(lambda wo: wo.id == target_id)
            if not target:
                raise UserError(_('Công đoạn trả về không hợp lệ.'))
            user_ids = [int(x) for x in form.getlist('assign_user_ids') if x]
            assign_users = request.env['res.users'].sudo().browse(user_ids).exists()
            review.action_fail(defect_reason_ids=reasons, note=note or False,
                               return_workorder_id=target, assign_user_ids=assign_users)
        else:
            raise UserError(_('Thao tác không hợp lệ.'))

    # ------------------------------------------------------------------
    # Lệnh sản xuất: danh sách công đoạn, chọn chế độ kiểm
    # ------------------------------------------------------------------
    def _production_detail_values(self, production, user, **extra):
        vals = super()._production_detail_values(production, user, **extra)
        vals.update({
            'portal_user': user,
            **self._review_common_values(),
        })
        return vals

    def _can_view_production(self, production, user):
        return user in production.user_mrp_stock_ids or production.workorder_ids._tiny_is_reviewer(user)

    @http.route('/my/productions/<int:production_id>', auth='user', website=True, type='http')
    def portal_production_detail(self, production_id, **kw):
        user = request.env.user
        production = request.env['mrp.production'].sudo().browse(production_id)
        if not production.exists() or not self._can_view_production(production, user):
            return request.not_found()
        return request.render('tiny_mrp.portal_production_detail',
                              self._production_detail_values(production, user))

    @http.route('/my/productions/<int:production_id>/action',
                auth='user', website=True, type='http', methods=['POST'])
    def portal_production_action(self, production_id, action=None, **kw):
        if action != 'set_review_mode':
            return super().portal_production_action(production_id, action=action, **kw)
        user = request.env.user
        production = request.env['mrp.production'].sudo().browse(production_id)
        if not production.exists() or not self._can_view_production(production, user):
            return request.not_found()
        error = None
        try:
            workorder = production.workorder_ids.filtered(lambda wo: str(wo.id) == str(kw.get('workorder_id')))
            if not workorder:
                raise UserError(_('Công đoạn không hợp lệ.'))
            mode = kw.get('review_mode')
            if mode not in _REVIEW_MODE_LABEL:
                raise UserError(_('Chế độ kiểm không hợp lệ.'))
            if not workorder.can_edit_review_mode:
                raise UserError(_('Bạn không được chọn chế độ kiểm cho công đoạn này.'))
            with request.env.cr.savepoint():
                workorder.write({'review_mode': mode})
        except UserError as e:
            error = e.args[0] if e.args else str(e)
        if error:
            return request.render('tiny_mrp.portal_production_detail',
                                  self._production_detail_values(production, user, error=error))
        return request.redirect('/my/productions/%d' % production_id)
