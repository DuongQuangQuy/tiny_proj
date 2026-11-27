from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import UserError
from odoo.addons.tiny_mrp.controller.main import (
    MrpPortal, _PRODUCTION_STATE_LABEL, _PRODUCTION_STATE_COLOR, _make_fmt_dt
)

_APPROVAL_STATUS_LABEL = {
    'new': 'Nháp',
    'pending': 'Chờ phê duyệt',
    'approved': 'Đã phê duyệt',
    'refused': 'Từ chối',
    'cancel': 'Đã hủy',
}

_APPROVAL_STATUS_COLOR = {
    'new': 'bg-secondary',
    'pending': 'bg-warning text-dark',
    'approved': 'bg-success',
    'refused': 'bg-danger',
    'cancel': 'bg-secondary',
}


class MrpApprovalsPortal(MrpPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'approval_count' in counters:
            values['approval_count'] = request.env['approval.request'].sudo().search_count([
                ('request_owner_id', '=', request.env.user.id),
                ('approval_type', '=', 'mrp_stock'),
                ('request_status', 'in', ('new', 'pending')),
            ])
        return values

    def _get_approval_request(self, approval_id):
        user = request.env.user
        approval = request.env['approval.request'].sudo().browse(approval_id)
        if not approval.exists():
            return None
        if approval.request_owner_id.id != user.id:
            return None
        if approval.approval_type != 'mrp_stock':
            return None
        return approval

    def _approval_detail_values(self, approval, **extra):
        products = request.env['product.product'].sudo().search(
            [('active', '=', True)], order='name'
        )
        vals = {
            'approval': approval,
            'fmt_dt': _make_fmt_dt(request.env),
            'page_name': 'approval',
            'approval_status_label': _APPROVAL_STATUS_LABEL,
            'approval_status_color': _APPROVAL_STATUS_COLOR,
            'products': products,
            'edit_line': None,
        }
        vals.update(extra)
        return vals

    @http.route('/my/approvals', auth='user', website=True, type='http')
    def portal_approvals(self, **kw):
        user = request.env.user
        approvals = request.env['approval.request'].sudo().search([
            ('request_owner_id', '=', user.id),
            ('approval_type', '=', 'mrp_stock'),
        ], order='id desc')
        return request.render('tiny_approvals_mrp.portal_my_approvals', {
            'approvals': approvals,
            'fmt_dt': _make_fmt_dt(request.env),
            'page_name': 'approval',
            'approval_status_label': _APPROVAL_STATUS_LABEL,
            'approval_status_color': _APPROVAL_STATUS_COLOR,
        })

    @http.route('/my/approvals/<int:approval_id>', auth='user', website=True, type='http')
    def portal_approval_detail(self, approval_id, edit=None, **kw):
        approval = self._get_approval_request(approval_id)
        if not approval:
            return request.not_found()
        edit_line = None
        if edit:
            try:
                line = request.env['approval.product.line'].sudo().browse(int(edit))
                if line.exists() and line.approval_request_id.id == approval_id:
                    edit_line = line
            except Exception:
                pass
        return request.render('tiny_approvals_mrp.portal_approval_detail',
                              self._approval_detail_values(approval, edit_line=edit_line))

    @http.route('/my/approvals/<int:approval_id>/action',
                auth='user', website=True, type='http', methods=['POST'])
    def portal_approval_action(self, approval_id, action=None, **kw):
        approval = self._get_approval_request(approval_id)
        if not approval:
            return request.not_found()
        error = None
        try:
            if action == 'confirm':
                if approval.request_status != 'new':
                    raise UserError(_('The request is not in draft.'))
                approval.action_confirm()
            elif action == 'draft':
                if approval.request_status not in ('pending', 'refused', 'cancel'):
                    raise UserError(_('Cannot reset to draft from the current state.'))
                approval.action_draft()
            else:
                raise UserError(_('Invalid action.'))
        except UserError as e:
            error = e.args[0] if e.args else str(e)
        except Exception as e:
            error = str(e)
        if error:
            return request.render('tiny_approvals_mrp.portal_approval_detail',
                                  self._approval_detail_values(approval, error=error))
        return request.redirect('/my/approvals/%d' % approval_id)

    @http.route('/my/approvals/<int:approval_id>/line/add',
                auth='user', website=True, type='http', methods=['POST'])
    def portal_approval_line_add(self, approval_id, product_id=None,
                                 description=None, quantity=None, **kw):
        approval = self._get_approval_request(approval_id)
        if not approval:
            return request.not_found()
        error = None
        try:
            if approval.request_status != 'new':
                raise UserError(_('Products can only be added while the request is in draft.'))
            if not product_id:
                raise UserError(_('Please select a product.'))
            try:
                qty = float(quantity or 1)
            except (ValueError, TypeError):
                qty = 1.0
            if qty <= 0:
                raise UserError(_('The quantity must be greater than 0.'))
            product = request.env['product.product'].sudo().browse(int(product_id))
            if not product.exists():
                raise UserError(_('Invalid product.'))
            desc = (description or '').strip() or product.description_purchase or product.display_name
            # Tạo theo công ty của phiếu: kho mặc định của dòng lấy theo env.company,
            # người dùng đang ở công ty thương mại sẽ bị lệch công ty
            request.env['approval.product.line'].sudo().with_company(approval.company_id).create({
                'approval_request_id': approval.id,
                'product_id': product.id,
                'description': desc,
                'quantity': qty,
            })
        except UserError as e:
            error = e.args[0] if e.args else str(e)
        except Exception as e:
            error = str(e)
        if error:
            return request.render('tiny_approvals_mrp.portal_approval_detail',
                                  self._approval_detail_values(approval, error=error))
        return request.redirect('/my/approvals/%d' % approval_id)

    @http.route('/my/approvals/<int:approval_id>/line/<int:line_id>/save',
                auth='user', website=True, type='http', methods=['POST'])
    def portal_approval_line_save(self, approval_id, line_id,
                                  product_id=None, description=None, quantity=None, **kw):
        approval = self._get_approval_request(approval_id)
        if not approval:
            return request.not_found()
        line = request.env['approval.product.line'].sudo().browse(line_id)
        if not line.exists() or line.approval_request_id.id != approval_id:
            return request.not_found()
        error = None
        try:
            if approval.request_status != 'new':
                raise UserError(_('The request can only be edited in draft.'))
            if not product_id:
                raise UserError(_('Please select a product.'))
            try:
                qty = float(quantity or 0)
            except (ValueError, TypeError):
                qty = 0.0
            if qty <= 0:
                raise UserError(_('The quantity must be greater than 0.'))
            product = request.env['product.product'].sudo().browse(int(product_id))
            if not product.exists():
                raise UserError(_('Invalid product.'))
            desc = (description or '').strip() or product.description_purchase or product.display_name
            line.write({
                'product_id': product.id,
                'description': desc,
                'quantity': qty,
            })
        except UserError as e:
            error = e.args[0] if e.args else str(e)
        except Exception as e:
            error = str(e)
        if error:
            return request.render('tiny_approvals_mrp.portal_approval_detail',
                                  self._approval_detail_values(approval, edit_line=line, error=error))
        return request.redirect('/my/approvals/%d' % approval_id)

    @http.route('/my/approvals/<int:approval_id>/line/<int:line_id>/delete',
                auth='user', website=True, type='http', methods=['POST'])
    def portal_approval_line_delete(self, approval_id, line_id, **kw):
        approval = self._get_approval_request(approval_id)
        if not approval:
            return request.not_found()
        line = request.env['approval.product.line'].sudo().browse(line_id)
        if not line.exists() or line.approval_request_id.id != approval_id:
            return request.not_found()
        error = None
        try:
            if approval.request_status != 'new':
                raise UserError(_('Lines can only be deleted while the request is in draft.'))
            line.unlink()
        except UserError as e:
            error = e.args[0] if e.args else str(e)
        except Exception as e:
            error = str(e)
        if error:
            return request.render('tiny_approvals_mrp.portal_approval_detail',
                                  self._approval_detail_values(approval, error=error))
        return request.redirect('/my/approvals/%d' % approval_id)

    def _get_stock_approval_request(self, production):
        return request.env['approval.request'].sudo().search([
            ('mrp_production_id', '=', production.id),
            ('approval_type', '=', 'mrp_stock'),
            ('request_status', 'not in', ('refused', 'cancel')),
        ], limit=1)

    def _production_detail_values(self, production, user, **extra):
        products = request.env['product.product'].sudo().search(
            [('active', '=', True)], order='name'
        ) if user.is_mrp_stock else request.env['product.product'].sudo().browse()
        vals = {
            'production': production,
            'fmt_dt': _make_fmt_dt(request.env),
            'page_name': 'production',
            'production_state_label': _PRODUCTION_STATE_LABEL,
            'production_state_color': _PRODUCTION_STATE_COLOR,
            'user_is_mrp': user.is_mrp_pattern,
            'user_is_mrp_stock': user.is_mrp_stock,
            'stock_approval': self._get_stock_approval_request(production),
            'products': products,
        }
        vals.update(extra)
        return vals

    @http.route('/my/productions/<int:production_id>', auth='user', website=True, type='http')
    def portal_production_detail(self, production_id, **kw):
        user = request.env.user
        production = request.env['mrp.production'].sudo().browse(production_id)
        if not production.exists() or user not in production.user_mrp_stock_ids:
            return request.not_found()
        return request.render('tiny_mrp.portal_production_detail',
                              self._production_detail_values(production, user))

    @http.route('/my/productions/<int:production_id>/action',
                auth='user', website=True, type='http', methods=['POST'])
    def portal_production_action(self, production_id, action=None, **kw):
        user = request.env.user
        production = request.env['mrp.production'].sudo().browse(production_id)
        if not production.exists() or user not in production.user_mrp_stock_ids:
            return request.not_found()

        if action != 'request_stock_approval':
            return super().portal_production_action(production_id, action=action, **kw)

        error = None
        try:
            if not user.is_mrp_stock:
                raise UserError(_('You are not allowed to perform this action.'))
            # Cho tạo phê duyệt cả khi kho chưa xác nhận: NVL có thể đã hết nên không xác nhận kho trước được
            if production.state_stock not in ('draft', 'confirmed'):
                raise UserError(_('The warehouse status is cancelled. Approval cannot be requested.'))
            mrp_company = request.env['res.company'].sudo().search(
                [('is_mrp', '=', True)], limit=1
            )
            if not mrp_company:
                raise UserError(_('No manufacturing company (is_mrp) is configured. Please contact your administrator.'))
            category = request.env['approval.category'].sudo().search([
                ('approval_type', '=', 'mrp_stock'),
                ('company_id', '=', mrp_company.id),
            ], limit=1)
            if not category:
                raise UserError(_('The approval type "MRP Stock Approval" is not configured for the manufacturing company. Please contact your administrator.'))

            product_ids = request.httprequest.form.getlist('product_ids[]')
            descriptions = request.httprequest.form.getlist('descriptions[]')
            quantities = request.httprequest.form.getlist('quantities[]')
            product_line_vals = []
            for i, pid in enumerate(product_ids):
                if not pid:
                    continue
                try:
                    qty = float(quantities[i]) if i < len(quantities) else 1.0
                except (ValueError, TypeError):
                    qty = 1.0
                product_line_vals.append((0, 0, {
                    'product_id': int(pid),
                    'description': descriptions[i] if i < len(descriptions) else '',
                    'quantity': qty,
                }))

            # Phiếu thuộc công ty sản xuất (theo loại phê duyệt): tạo trong ngữ cảnh công ty đó để
            # kho mặc định của các dòng sản phẩm cùng công ty với phiếu
            approval = request.env['approval.request'].sudo().with_company(category.company_id).create({
                'name': _('Stock Issue Approval - %s') % production.name,
                'category_id': category.id,
                'mrp_production_id': production.id,
                'request_owner_id': user.id,
                'product_line_ids': product_line_vals,
            })
            approval.action_confirm()
        except UserError as e:
            error = e.args[0] if e.args else str(e)
        except Exception as e:
            error = str(e)

        if error:
            return request.render('tiny_mrp.portal_production_detail',
                                  self._production_detail_values(production, user, error=error))

        return request.redirect('/my/productions/%d' % production_id)
