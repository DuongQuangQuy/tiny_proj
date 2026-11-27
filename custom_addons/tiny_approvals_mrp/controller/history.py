from odoo import http
from odoo.http import request
from odoo.osv import expression
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.tiny_mrp.controller.main import (
    _make_fmt_dt, _STATE_LABEL, _STATE_COLOR,
)

from .review import MrpReviewPortal

_HISTORY_PAGE_SIZE = 20

_HISTORY_FILTERS = {
    'all': ('Tất cả', []),
    'done': ('Hoàn thành', [('state', '=', 'done')]),
    'open': ('Chưa hoàn thành', [('state', 'not in', ('done', 'cancel'))]),
    'rework': ('Có chỉnh sửa', [('rework_count', '>', 0)]),
}

_RETURN_STATE_LABEL = {
    'open': 'Đang chỉnh',
    'done': 'Đã chỉnh xong',
    'cancel': 'Đã hủy',
}

_RETURN_STATE_COLOR = {
    'open': 'bg-danger',
    'done': 'bg-success',
    'cancel': 'bg-secondary',
}


class MrpHistoryPortal(MrpReviewPortal):

    # ------------------------------------------------------------------
    # Tiện ích
    # ------------------------------------------------------------------
    def _history_domain(self, user):
        """Công đoạn nhân viên đã làm: có bấm giờ, hoặc được giao và đã hoàn thành."""
        return [
            '|',
            ('time_ids.user_mrp_id', '=', user.id),
            '&', ('user_mrp_ids', 'in', user.id), ('state', '=', 'done'),
        ]

    def _history_user_durations(self, workorders, user):
        """Tổng phút làm mới / làm sửa của chính nhân viên trên từng công đoạn."""
        result = {wo.id: {'new': 0.0, 'rework': 0.0} for wo in workorders}
        if not workorders:
            return result
        groups = request.env['mrp.workcenter.productivity'].sudo()._read_group(
            [('workorder_id', 'in', workorders.ids), ('user_mrp_id', '=', user.id)],
            groupby=['workorder_id', 'work_type'], aggregates=['duration:sum'])
        for workorder, work_type, duration in groups:
            key = 'rework' if work_type == 'rework' else 'new'
            result[workorder.id][key] += duration or 0.0
        return result

    def _history_review_stats(self, workorder):
        reviews = workorder.review_ids.filtered(lambda r: r.state != 'cancel')
        return {
            'review_count': len(reviews),
            'failed_count': len(reviews.filtered(lambda r: r.state == 'failed')),
        }

    def _history_common_values(self):
        return {
            'page_name': 'workorder_history',
            'state_label': dict(_STATE_LABEL, cancel='Đã hủy'),
            'state_color': dict(_STATE_COLOR, cancel='bg-secondary'),
            'return_state_label': _RETURN_STATE_LABEL,
            'return_state_color': _RETURN_STATE_COLOR,
            'fmt_dt': _make_fmt_dt(request.env),
            **self._review_common_values(),
        }

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'workorder_history_count' in counters:
            values['workorder_history_count'] = request.env['mrp.workorder'].sudo().search_count(
                self._history_domain(request.env.user))
        return values

    # ------------------------------------------------------------------
    # Danh sách lịch sử
    # ------------------------------------------------------------------
    @http.route(['/my/workorder-history', '/my/workorder-history/page/<int:page>'],
                auth='user', website=True, type='http')
    def portal_workorder_history(self, page=1, filterby='all', search='', **kw):
        user = request.env.user
        Workorder = request.env['mrp.workorder'].sudo()
        if filterby not in _HISTORY_FILTERS:
            filterby = 'all'
        search = (search or '').strip()

        domain = expression.AND([self._history_domain(user), _HISTORY_FILTERS[filterby][1]])
        if search:
            domain = expression.AND([domain, [
                '|', '|', '|', '|',
                ('name', 'ilike', search),
                ('production_id.name', 'ilike', search),
                ('production_id.full_name', 'ilike', search),
                ('production_id.product_id.name', 'ilike', search),
                ('production_id.product_id.default_code', 'ilike', search),
            ]])

        total = Workorder.search_count(domain)
        pager = portal_pager(
            url='/my/workorder-history',
            url_args={'filterby': filterby, 'search': search},
            total=total, page=page, step=_HISTORY_PAGE_SIZE,
        )
        workorders = Workorder.search(
            domain, order='date_finished desc nulls last, id desc',
            limit=_HISTORY_PAGE_SIZE, offset=pager['offset'])

        durations = self._history_user_durations(workorders, user)
        review_stats = {wo.id: self._history_review_stats(wo) for wo in workorders}
        return request.render('tiny_approvals_mrp.portal_my_workorder_history', {
            'workorders': workorders,
            'durations': durations,
            'review_stats': review_stats,
            'pager': pager,
            'total': total,
            'filterby': filterby,
            'filters': {key: label for key, (label, _domain) in _HISTORY_FILTERS.items()},
            'search': search,
            **self._history_common_values(),
        })

    # ------------------------------------------------------------------
    # Chi tiết lịch sử 1 công đoạn
    # ------------------------------------------------------------------
    @http.route('/my/workorder-history/<int:workorder_id>', auth='user', website=True, type='http')
    def portal_workorder_history_detail(self, workorder_id, **kw):
        user = request.env.user
        workorder = request.env['mrp.workorder'].sudo().search(
            expression.AND([[('id', '=', workorder_id)], self._history_domain(user)]), limit=1)
        if not workorder:
            return request.not_found()

        my_times = workorder.time_ids.filtered(lambda t: t.user_mrp_id == user).sorted('date_start')
        durations = self._history_user_durations(workorder, user)[workorder.id]
        returns = workorder.return_ids.filtered(lambda r: r.state != 'cancel').sorted('id')
        return request.render('tiny_approvals_mrp.portal_workorder_history_detail', {
            'workorder': workorder,
            'my_times': my_times,
            'my_duration_new': durations['new'],
            'my_duration_rework': durations['rework'],
            'review_history': workorder.review_ids.sorted(lambda r: (r.round_no, r.id)),
            'review_stats': self._history_review_stats(workorder),
            'returns': returns,
            # Lượt nhân viên này trả về công đoạn trước
            'returns_out': workorder.env['mrp.workorder.return'].search(
                [('from_workorder_id', '=', workorder.id), ('state', '!=', 'cancel')], order='id'),
            'product_image_src': self._get_product_image_src(workorder.production_id.product_id),
            **self._history_common_values(),
        })
