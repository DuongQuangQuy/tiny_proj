from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    @api.constrains('code', 'company_id')
    def _check_code_unique_in_company(self):
        """Khu vực 2 công ty nối với nhau bằng mã, nên mã phải duy nhất trong từng công ty."""
        for workcenter in self.filtered('code'):
            if self.sudo().search_count([
                ('id', '!=', workcenter.id),
                ('code', '=', workcenter.code),
                ('company_id', '=', workcenter.company_id.id),
            ], limit=1):
                raise ValidationError(_('Mã khu vực sản xuất %s đã được dùng trong công ty này.', workcenter.code))

    @api.model
    def web_name_search(self, name, specification, domain=None, operator='ilike', limit=100):
        """Dự toán chọn khu vực của công ty hiện tại đã có khu vực cùng mã ở công ty sản xuất.
        Nhân viên bán hàng không có quyền đọc khu vực nên chỉ lấy id và tên qua sudo."""
        if self.env.context.get('sale_estimate_workcenter') and self.env.user.has_group('sales_team.group_sale_salesman'):
            mrp_company = self.env['sale.estimate']._get_mrp_company()
            mrp_codes = self.sudo().search([('company_id', '=', mrp_company.id), ('code', '!=', False)]).mapped('code')
            domain = Domain(domain or []) & Domain('company_id', '=', self.env.company.id) & Domain('code', 'in', mrp_codes)
            return super(MrpWorkcenter, self.sudo()).web_name_search(
                name, {'display_name': {}}, domain, operator, limit)
        return super().web_name_search(name, specification, domain, operator, limit)
