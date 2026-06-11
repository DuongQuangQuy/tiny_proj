import pytz

from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError
from odoo.addons.portal.controllers.portal import CustomerPortal


def _make_fmt_dt(env):
    tz_name = env.context.get('tz') or env.user.tz or 'UTC'
    tz = pytz.timezone(tz_name)
    def fmt_dt(dt):
        if not dt:
            return '—'
        return pytz.utc.localize(dt).astimezone(tz).strftime('%d/%m/%Y %H:%M')
    return fmt_dt

_STATE_LABEL = {
    'pending': 'Chờ xử lý',
    'waiting': 'Chờ vật tư',
    'ready': 'Sẵn sàng',
    'progress': 'Đang thực hiện',
    'done': 'Hoàn thành',
    'blocked': 'Bị chặn',
}

_STATE_COLOR = {
    'pending': 'bg-warning text-dark',
    'waiting': 'bg-info text-dark',
    'ready': 'bg-success',
    'progress': 'bg-primary',
    'done': 'bg-secondary',
    'blocked': 'bg-danger',
}


class MrpPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'workorder_count' in counters:
            user = request.env.user
            values['workorder_count'] = request.env['mrp.workorder'].sudo().search_count([
                ('user_mrp_ids', 'in', user.id)
            ])
        return values

    @http.route('/my/workorders', auth='user', website=True, type='http')
    def portal_workorders(self, **kw):
        user = request.env.user
        workorders = request.env['mrp.workorder'].sudo().search([
            ('user_mrp_ids', 'in', user.id), ('state', 'not in', ('done', 'cancel'))
        ], order='id desc')
        return request.render('tiny_mrp.portal_my_workorders', {
            'workorders': workorders,
            'page_name': 'workorder',
            'state_label': _STATE_LABEL,
            'state_color': _STATE_COLOR,
        })

    @http.route('/my/workorders/<int:workorder_id>', auth='user', website=True, type='http')
    def portal_workorder_detail(self, workorder_id, **kw):
        user = request.env.user
        workorder = request.env['mrp.workorder'].sudo().browse(workorder_id)
        if not workorder.exists() or user not in workorder.user_mrp_ids:
            return request.not_found()
        has_open_time = bool(workorder.time_ids.filtered(lambda t: not t.date_end))
        return request.render('tiny_mrp.portal_workorder_detail', {
            'workorder': workorder,
            'has_open_time': has_open_time,
            'fmt_dt': _make_fmt_dt(request.env),
            'page_name': 'workorder',
            'state_label': _STATE_LABEL,
            'state_color': _STATE_COLOR,
        })

    @http.route('/my/workorders/<int:workorder_id>/action', auth='user', website=True, type='http', methods=['POST'])
    def portal_workorder_action(self, workorder_id, action=None, **kw):
        user = request.env.user
        workorder = request.env['mrp.workorder'].sudo().browse(workorder_id)
        if not workorder.exists() or user not in workorder.user_mrp_ids:
            return request.not_found()

        error = None
        try:
            if workorder.working_state == 'blocked':
                raise UserError(_('Trạm làm việc đang bị chặn, không thể thực hiện thao tác.'))
            if workorder.production_state in ('draft', 'done', 'cancel'):
                raise UserError(_('Lệnh sản xuất không ở trạng thái cho phép thao tác.'))
            if workorder.state in ('done', 'cancel'):
                raise UserError(_('Lệnh công việc đã kết thúc hoặc bị hủy.'))

            has_open_time = bool(workorder.time_ids.filtered(lambda t: not t.date_end))

            if action == 'start':
                if has_open_time:
                    raise UserError(_('Lệnh công việc đang có phiên làm việc chưa kết thúc, hãy tạm dừng trước.'))
                workorder.with_context(portal_user_id=user.id).button_start(bypass=True)
            elif action == 'pending':
                if not has_open_time or workorder.state != 'progress':
                    raise UserError(_('Thao tác không hợp lệ. Không có phiên làm việc nào đang mở.'))
                workorder.with_context(portal_user_id=user.id).button_pending()
            elif action == 'finish':
                if workorder.state != 'progress':
                    raise UserError(_('Thao tác không hợp lệ. Lệnh công việc không đang trong trạng thái thực hiện.'))
                workorder.with_context(portal_user_id=user.id).button_finish()
            else:
                raise UserError(_('Thao tác không hợp lệ.'))
        except UserError as e:
            error = e.args[0] if e.args else str(e)
        except Exception as e:
            error = str(e)

        if error:
            has_open_time = bool(workorder.time_ids.filtered(lambda t: not t.date_end))
            return request.render('tiny_mrp.portal_workorder_detail', {
                'workorder': workorder,
                'has_open_time': has_open_time,
                'fmt_dt': _make_fmt_dt(request.env),
                'page_name': 'workorder',
                'state_label': _STATE_LABEL,
                'state_color': _STATE_COLOR,
                'error': error,
            })

        return request.redirect('/my/workorders/%d' % workorder_id)

    @http.route('/my/workorders/<int:workorder_id>/productivity', auth='user', website=True, type='http')
    def portal_workorder_productivity(self, workorder_id, **kw):
        user = request.env.user
        workorder = request.env['mrp.workorder'].sudo().browse(workorder_id)
        if not workorder.exists() or user not in workorder.user_mrp_ids:
            return request.not_found()
        return request.render('tiny_mrp.portal_workorder_productivity', {
            'workorder': workorder,
            'productivities': workorder.time_ids.sorted('date_start', reverse=True),
            'fmt_dt': _make_fmt_dt(request.env),
            'page_name': 'workorder',
            'state_label': _STATE_LABEL,
            'state_color': _STATE_COLOR,
        })
