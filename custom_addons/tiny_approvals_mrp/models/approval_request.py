import logging
from datetime import datetime
from pytz import timezone, UTC

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.date_utils import float_to_time
from odoo.tools.misc import formatLang
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    mrp_production_id = fields.Many2one('mrp.production', string='Manufacturing Order')

    def action_confirm(self):
        pending_before = self.approver_ids.filtered(lambda a: a.status == 'pending')
        res = super().action_confirm()
        # Phiếu phê duyệt mua hàng (mrp_stock): nhắn tin cho người duyệt vừa đến lượt duyệt.
        # Áp dụng cho mọi cách nộp: portal từ lệnh sản xuất, portal tạo trực tiếp, nút Nộp trên backend.
        # Lỗi khi gửi tin chỉ ghi log, không chặn việc nộp phiếu.
        if self.approval_type == 'mrp_stock':
            approvers = self.approver_ids.filtered(lambda a: a.status == 'pending') - pending_before
            try:
                with self.env.cr.savepoint():
                    self._notify_mrp_stock_approvers(approvers)
            except Exception:
                _logger.exception('Could not notify approvers of approval request %s', self.id)
        return res

    def _notify_mrp_stock_approvers(self, approvers):
        self.ensure_one()
        partners = approvers.user_id.partner_id
        if not partners:
            _logger.warning('Approval request %s submitted but has no approver to notify', self.id)
            return
        production = self.mrp_production_id
        lines = Markup('').join(
            Markup('<li>%s: %s %s</li>') % (
                line.product_id.display_name or line.description or '',
                formatLang(self.env, line.quantity, dp='Product Unit'),
                line.product_uom_id.name or '',
            ) for line in self.product_line_ids
        )
        body = Markup('<p>%s</p>') % _(
            '%(owner)s submitted the purchase approval request "%(name)s" and is waiting for your approval.',
            owner=self.request_owner_id.name, name=self.name)
        if production:
            body += Markup('<p>%s</p>') % _(
                'Manufacturing order: %s', production.full_name or production.name)
        if lines:
            body += Markup('<p>%s</p><ul>%s</ul>') % (_('Products:'), lines)
        self.message_post(
            body=body,
            partner_ids=partners.ids,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

    def action_view_mrp_production(self):
        """Smart button: mở lệnh sản xuất của phiếu phê duyệt."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Manufacturing Order'),
            'res_model': 'mrp.production',
            'view_mode': 'form',
            'res_id': self.mrp_production_id.id,
        }
