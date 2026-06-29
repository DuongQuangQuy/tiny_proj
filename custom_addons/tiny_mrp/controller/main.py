import pytz

from odoo import http, fields, _
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

_PRODUCTION_STATE_LABEL = {
    'draft': 'Nháp',
    'confirmed': 'Đã xác nhận',
    'progress': 'Đang thực hiện',
    'to_close': 'Cần đóng',
    'done': 'Hoàn thành',
    'cancel': 'Đã hủy',
}

_PRODUCTION_STATE_COLOR = {
    'draft': 'bg-secondary',
    'confirmed': 'bg-info text-dark',
    'progress': 'bg-primary',
    'to_close': 'bg-warning text-dark',
    'done': 'bg-success',
    'cancel': 'bg-danger',
}

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
        if 'production_count' in counters:
            user = request.env.user
            values['production_count'] = request.env['mrp.production'].sudo().search_count([
                ('user_mrp_stock_ids', 'in', user.id),
                ('state', 'in', ('draft', 'confirmed')),
            ])
        return values

    @http.route('/my/workorders', auth='user', website=True, type='http')
    def portal_workorders(self, **kw):
        user = request.env.user
        workorders = request.env['mrp.workorder'].sudo().search([
            ('user_mrp_ids', 'in', user.id),
            ('state', 'not in', ('done', 'cancel')),
            ('production_id.date_start', '<=', fields.Datetime.now()),
            '|',
            ('production_id.is_mrp_pattern', '=', True),
            ('production_id.state_stock', '=', 'confirmed'),
        ])
        workorders = workorders.sorted(key=lambda wo: (wo.production_id.date_start or fields.Datetime.max, wo.id))
        active_times = request.env['mrp.workcenter.productivity'].sudo().search([
            ('user_mrp_id', '=', user.id),
            ('date_end', '=', False),
        ])
        active_wo_ids = set(active_times.mapped('workorder_id').ids)
        return request.render('tiny_mrp.portal_my_workorders', {
            'workorders': workorders,
            'active_wo_ids': active_wo_ids,
            'page_name': 'workorder',
            'state_label': _STATE_LABEL,
            'state_color': _STATE_COLOR,
        })

    def _get_product_image_src(self, product):
        if not product:
            return ''
        img = product.sudo().image_1920 or product.sudo().image_512 or product.sudo().image_256
        if not img:
            return ''
        if isinstance(img, bytes):
            img = img.decode('utf-8')
        return 'data:image/png;base64,' + img

    def _get_user_other_active_workorder(self, user, exclude_workorder_id):
        return request.env['mrp.workcenter.productivity'].sudo().search([
            ('user_mrp_id', '=', user.id),
            ('date_end', '=', False),
            ('workorder_id', '!=', exclude_workorder_id),
        ], limit=1)

    @http.route('/my/workorders/<int:workorder_id>', auth='user', website=True, type='http')
    def portal_workorder_detail(self, workorder_id, **kw):
        user = request.env.user
        workorder = request.env['mrp.workorder'].sudo().browse(workorder_id)
        if not workorder.exists() or user not in workorder.user_mrp_ids:
            return request.not_found()
        has_open_time = bool(workorder.time_ids.filtered(lambda t: not t.date_end))
        other_active = self._get_user_other_active_workorder(user, workorder.id)
        product = workorder.production_id.product_id
        mrp_reasons = request.env['mrp.reason'].sudo().search([])
        return request.render('tiny_mrp.portal_workorder_detail', {
            'workorder': workorder,
            'has_open_time': has_open_time,
            'has_other_active': bool(other_active),
            'other_active_name': other_active.workorder_id.name if other_active else '',
            'product_image_src': self._get_product_image_src(product),
            'fmt_dt': _make_fmt_dt(request.env),
            'page_name': 'workorder',
            'state_label': _STATE_LABEL,
            'state_color': _STATE_COLOR,
            'mrp_reasons': mrp_reasons,
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
                other_active = self._get_user_other_active_workorder(user, workorder.id)
                if other_active:
                    raise UserError(_('Bạn đang thực hiện công đoạn "%s". Hãy tạm dừng trước khi bắt đầu công đoạn mới.' % other_active.workorder_id.name))
                workorder.with_context(portal_user_id=user.id).button_start(bypass=True)
            elif action == 'pending':
                reason_id = kw.get('reason_id', '').strip()
                if not reason_id:
                    raise UserError(_('Vui lòng chọn lý do tạm dừng.'))
                reason = request.env['mrp.reason'].sudo().browse(int(reason_id))
                if not reason.exists():
                    raise UserError(_('Lý do tạm dừng không hợp lệ.'))
                if not has_open_time or workorder.state != 'progress':
                    raise UserError(_('Thao tác không hợp lệ. Không có phiên làm việc nào đang mở.'))
                workorder.with_context(portal_user_id=user.id).button_pending()
                request.env['mrp.pause.reason'].sudo().create({
                    'reason_id': reason.id,
                    'user_id': user.id,
                    'workorder_id': workorder.id,
                })
            elif action == 'finish':
                if workorder.state != 'progress':
                    raise UserError(_('Thao tác không hợp lệ. Lệnh công việc không đang trong trạng thái thực hiện.'))
                workorder.with_context(portal_user_id=user.id).button_finish()
                production = workorder.production_id
                if (production.is_mrp_pattern
                        and production.state not in ('done', 'cancel')
                        and all(wo.state == 'done' for wo in production.workorder_ids)):
                    production.action_done_pattern()
            else:
                raise UserError(_('Thao tác không hợp lệ.'))
        except UserError as e:
            error = e.args[0] if e.args else str(e)
        except Exception as e:
            error = str(e)

        if error:
            has_open_time = bool(workorder.time_ids.filtered(lambda t: not t.date_end))
            other_active = self._get_user_other_active_workorder(user, workorder.id)
            product = workorder.production_id.product_id
            mrp_reasons = request.env['mrp.reason'].sudo().search([])
            return request.render('tiny_mrp.portal_workorder_detail', {
                'workorder': workorder,
                'has_open_time': has_open_time,
                'has_other_active': bool(other_active),
                'other_active_name': other_active.workorder_id.name if other_active else '',
                'product_image_src': self._get_product_image_src(product),
                'fmt_dt': _make_fmt_dt(request.env),
                'page_name': 'workorder',
                'state_label': _STATE_LABEL,
                'state_color': _STATE_COLOR,
                'mrp_reasons': mrp_reasons,
                'error': error,
            })

        return request.redirect('/my/workorders/%d' % workorder_id)

    @http.route('/my/productions', auth='user', website=True, type='http')
    def portal_productions(self, **kw):
        user = request.env.user
        MrpProduction = request.env['mrp.production'].sudo()
        base_domain = [
            ('user_mrp_stock_ids', 'in', user.id),
            ('state', 'in', ('draft', 'confirmed','progress')),
        ]
        productions_main = MrpProduction.search(
            base_domain + [('is_mrp_pattern', '=', False)], order='id desc'
        )
        productions_sub = MrpProduction.search([
            ('user_mrp_stock_ids', 'in', user.id),
            ('is_mrp_pattern', '=', True),
            ('state', '!=', 'cancel'),
        ], order='id desc') if user.is_mrp_pattern else MrpProduction.browse()
        return request.render('tiny_mrp.portal_my_productions', {
            'productions_main': productions_main,
            'productions_sub': productions_sub,
            'user_is_mrp': user.is_mrp_pattern,
            'page_name': 'production',
            'production_state_label': _PRODUCTION_STATE_LABEL,
            'production_state_color': _PRODUCTION_STATE_COLOR,
        })

    @http.route('/my/productions/<int:production_id>', auth='user', website=True, type='http')
    def portal_production_detail(self, production_id, **kw):
        user = request.env.user
        production = request.env['mrp.production'].sudo().browse(production_id)
        if not production.exists() or user not in production.user_mrp_stock_ids:
            return request.not_found()
        return request.render('tiny_mrp.portal_production_detail', {
            'production': production,
            'fmt_dt': _make_fmt_dt(request.env),
            'page_name': 'production',
            'production_state_label': _PRODUCTION_STATE_LABEL,
            'production_state_color': _PRODUCTION_STATE_COLOR,
            'user_is_mrp': user.is_mrp_pattern,
            'user_is_mrp_stock': user.is_mrp_stock,
        })

    @http.route('/my/productions/<int:production_id>/action', auth='user', website=True, type='http', methods=['POST'])
    def portal_production_action(self, production_id, action=None, **kw):
        user = request.env.user
        production = request.env['mrp.production'].sudo().browse(production_id)
        if not production.exists() or user not in production.user_mrp_stock_ids:
            return request.not_found()

        error = None
        try:
            if action == 'confirm':
                if not user.is_mrp_pattern:
                    raise UserError(_('Bạn không có quyền thực hiện thao tác này.'))
                if production.state != 'draft':
                    raise UserError(_('Lệnh sản xuất không ở trạng thái nháp.'))
                production.action_confirm()
            elif action == 'confirm_pattern':
                if not user.is_mrp_pattern:
                    raise UserError(_('Bạn không có quyền thực hiện thao tác này.'))
                if production.state != 'confirmed':
                    raise UserError(_('Lệnh sản xuất chưa được xác nhận, không thể xác nhận rập.'))
                if production.state_pattern != 'draft':
                    raise UserError(_('Trạng thái rập đã được xác nhận.'))
                production.action_confirm_pattern()
            elif action == 'confirm_stock':
                if not user.is_mrp_stock:
                    raise UserError(_('Bạn không có quyền thực hiện thao tác này.'))
                if production.state_stock != 'draft':
                    raise UserError(_('Trạng thái kho đã được xác nhận.'))
                production.action_confirm_stock()
            elif action == 'done_pattern':
                if not user.is_mrp_pattern:
                    raise UserError(_('Bạn không có quyền thực hiện thao tác này.'))
                if not production.is_mrp_pattern:
                    raise UserError(_('Đây không phải là lệnh rập.'))
                if production.state in ('done', 'cancel'):
                    raise UserError(_('Lệnh sản xuất đã hoàn thành hoặc bị hủy.'))
                production.action_done_pattern()
            else:
                raise UserError(_('Thao tác không hợp lệ.'))
        except UserError as e:
            error = e.args[0] if e.args else str(e)
        except Exception as e:
            error = str(e)

        if error:
            return request.render('tiny_mrp.portal_production_detail', {
                'production': production,
                'fmt_dt': _make_fmt_dt(request.env),
                'page_name': 'production',
                'production_state_label': _PRODUCTION_STATE_LABEL,
                'production_state_color': _PRODUCTION_STATE_COLOR,
                'error': error,
                'user_is_mrp': user.is_mrp_pattern,
                'user_is_mrp_stock': user.is_mrp_stock,
            })

        return request.redirect('/my/productions/%d' % production_id)

    def _portal_move_ctx(self, production, move, **extra):
        user = request.env.user
        return {
            'production': production,
            'move': move,
            'page_name': 'production',
            'production_state_label': _PRODUCTION_STATE_LABEL,
            'production_state_color': _PRODUCTION_STATE_COLOR,
            'user_is_mrp_stock': user.is_mrp_stock,
            'user_can_edit_move': user.is_mrp_stock or user.is_mrp_pattern,
            **extra,
        }

    @http.route('/my/productions/<int:production_id>/move/<int:move_id>', auth='user', website=True, type='http')
    def portal_production_move_detail(self, production_id, move_id, edit=None, **kw):
        user = request.env.user
        production = request.env['mrp.production'].sudo().browse(production_id)
        if not production.exists() or user not in production.user_mrp_stock_ids or not (user.is_mrp_stock or user.is_mrp_pattern):
            return request.not_found()
        move = request.env['stock.move'].sudo().browse(move_id)
        if not move.exists() or move.raw_material_production_id.id != production_id:
            return request.not_found()
        edit_line = None
        if edit:
            try:
                edit_line = request.env['stock.move.line'].sudo().browse(int(edit))
                if not edit_line.exists() or edit_line.move_id.id != move_id:
                    edit_line = None
            except Exception:
                edit_line = None
        available_quants = request.env['stock.quant'].sudo().search([
            ('product_id', '=', move.product_id.id),
            ('location_id', 'child_of', move.location_id.id),
            ('quantity', '>', 0),
        ], order='lot_id asc, location_id asc').filtered(lambda q: q.available_quantity > 0)
        return request.render('tiny_mrp.portal_production_move_detail',
            self._portal_move_ctx(production, move, edit_line=edit_line,
                                  available_quants=available_quants))

    @http.route('/my/productions/<int:production_id>/move/<int:move_id>/save', auth='user', website=True, type='http', methods=['POST'])
    def portal_production_move_save(self, production_id, move_id, product_uom_qty=None, **kw):
        user = request.env.user
        production = request.env['mrp.production'].sudo().browse(production_id)
        if not production.exists() or user not in production.user_mrp_stock_ids or not (user.is_mrp_stock or user.is_mrp_pattern):
            return request.not_found()
        move = request.env['stock.move'].sudo().browse(move_id)
        if not move.exists() or move.raw_material_production_id.id != production_id:
            return request.not_found()
        error = None
        try:
            if production.state not in ('draft', 'confirmed', 'progress'):
                raise UserError(_('Lệnh sản xuất không ở trạng thái cho phép chỉnh sửa.'))
            qty = float(product_uom_qty or 0)
            if qty <= 0:
                raise UserError(_('Số lượng phải lớn hơn 0.'))
            move.write({'product_uom_qty': qty})
        except (UserError, ValueError) as e:
            error = e.args[0] if hasattr(e, 'args') and e.args else str(e)
        except Exception as e:
            error = str(e)
        if error:
            return request.render('tiny_mrp.portal_production_move_detail',
                self._portal_move_ctx(production, move, error=error))
        return request.redirect('/my/productions/%d/move/%d' % (production_id, move_id))

    @http.route('/my/productions/<int:production_id>/move/<int:move_id>/add-line', auth='user', website=True, type='http', methods=['POST'])
    def portal_production_move_add_line(self, production_id, move_id, quant_id=None, lot_name=None, quantity=None, **kw):
        user = request.env.user
        production = request.env['mrp.production'].sudo().browse(production_id)
        if not production.exists() or user not in production.user_mrp_stock_ids or not user.is_mrp_stock:
            return request.not_found()
        move = request.env['stock.move'].sudo().browse(move_id)
        if not move.exists() or move.raw_material_production_id.id != production_id:
            return request.not_found()
        error = None
        try:
            if production.state not in ('draft', 'confirmed', 'progress'):
                raise UserError(_('Lệnh sản xuất không ở trạng thái cho phép chỉnh sửa.'))
            vals = {
                'move_id': move.id,
                'product_id': move.product_id.id,
                'product_uom_id': move.product_uom.id,
                'location_id': move.location_id.id,
                'location_dest_id': move.location_dest_id.id,
                'company_id': move.company_id.id,
            }
            if quant_id:
                quant = request.env['stock.quant'].sudo().browse(int(quant_id))
                if not quant.exists() or quant.product_id.id != move.product_id.id:
                    raise UserError(_('Lô hàng không hợp lệ.'))
                done_qty = sum(move.move_line_ids.mapped('quantity'))
                remaining = max(0.0, move.product_uom_qty - done_qty)
                auto_qty = max(0.0, min(quant.available_quantity, remaining)) if remaining > 0 else quant.available_quantity
                if auto_qty <= 0:
                    raise UserError(_('Không còn số lượng khả dụng trên lô này.'))
                vals.update({
                    'lot_id': quant.lot_id.id if quant.lot_id else False,
                    'location_id': quant.location_id.id,
                    'quantity': auto_qty,
                })
            else:
                qty = float(quantity or 0)
                if qty <= 0:
                    raise UserError(_('Số lượng phải lớn hơn 0.'))
                vals.update({
                    'lot_name': lot_name.strip() if lot_name and lot_name.strip() else False,
                    'quantity': qty,
                })
            request.env['stock.move.line'].sudo().create(vals)
        except (UserError, ValueError) as e:
            error = e.args[0] if hasattr(e, 'args') and e.args else str(e)
        except Exception as e:
            error = str(e)
        if error:
            available_quants = request.env['stock.quant'].sudo().search([
                ('product_id', '=', move.product_id.id),
                ('location_id', 'child_of', move.location_id.id),
                ('quantity', '>', 0),
            ], order='lot_id asc, location_id asc').filtered(lambda q: q.available_quantity > 0)
            return request.render('tiny_mrp.portal_production_move_detail',
                self._portal_move_ctx(production, move, error=error,
                                      available_quants=available_quants))
        return request.redirect('/my/productions/%d/move/%d' % (production_id, move_id))

    @http.route('/my/productions/<int:production_id>/move/<int:move_id>/line/<int:line_id>/save', auth='user', website=True, type='http', methods=['POST'])
    def portal_production_move_line_save(self, production_id, move_id, line_id, lot_name=None, quantity=None, **kw):
        user = request.env.user
        production = request.env['mrp.production'].sudo().browse(production_id)
        if not production.exists() or user not in production.user_mrp_stock_ids or not user.is_mrp_stock:
            return request.not_found()
        move = request.env['stock.move'].sudo().browse(move_id)
        if not move.exists() or move.raw_material_production_id.id != production_id:
            return request.not_found()
        line = request.env['stock.move.line'].sudo().browse(line_id)
        if not line.exists() or line.move_id.id != move_id:
            return request.not_found()
        error = None
        try:
            if production.state not in ('draft', 'confirmed', 'progress'):
                raise UserError(_('Lệnh sản xuất không ở trạng thái cho phép chỉnh sửa.'))
            qty = float(quantity or 0)
            if qty <= 0:
                raise UserError(_('Số lượng phải lớn hơn 0.'))
            line.write({
                'lot_name': lot_name.strip() if lot_name and lot_name.strip() else False,
                'quantity': qty,
            })
        except (UserError, ValueError) as e:
            error = e.args[0] if hasattr(e, 'args') and e.args else str(e)
        except Exception as e:
            error = str(e)
        if error:
            return request.render('tiny_mrp.portal_production_move_detail',
                self._portal_move_ctx(production, move, edit_line=line, error=error))
        return request.redirect('/my/productions/%d/move/%d' % (production_id, move_id))

    @http.route('/my/productions/<int:production_id>/move/<int:move_id>/line/<int:line_id>/delete', auth='user', website=True, type='http', methods=['POST'])
    def portal_production_move_line_delete(self, production_id, move_id, line_id, **kw):
        user = request.env.user
        production = request.env['mrp.production'].sudo().browse(production_id)
        if not production.exists() or user not in production.user_mrp_stock_ids or not user.is_mrp_stock:
            return request.not_found()
        move = request.env['stock.move'].sudo().browse(move_id)
        if not move.exists() or move.raw_material_production_id.id != production_id:
            return request.not_found()
        line = request.env['stock.move.line'].sudo().browse(line_id)
        if not line.exists() or line.move_id.id != move_id:
            return request.not_found()
        error = None
        try:
            if production.state not in ('draft', 'confirmed', 'progress'):
                raise UserError(_('Lệnh sản xuất không ở trạng thái cho phép chỉnh sửa.'))
            line.unlink()
        except (UserError, Exception) as e:
            error = e.args[0] if hasattr(e, 'args') and e.args else str(e)
        if error:
            return request.render('tiny_mrp.portal_production_move_detail',
                self._portal_move_ctx(production, move, error=error))
        return request.redirect('/my/productions/%d/move/%d' % (production_id, move_id))

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
