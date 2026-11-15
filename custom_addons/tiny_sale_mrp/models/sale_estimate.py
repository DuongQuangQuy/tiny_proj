from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round


class SaleEstimate(models.Model):
    _name = 'sale.estimate'
    _description = 'Phiếu dự toán'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(string='Số phiếu', required=True, copy=False, readonly=True, default=lambda self: _('Mới'))
    estimate_type = fields.Selection([
        ('order', 'Dự toán đơn hàng'),
        ('price', 'Tính giá sản phẩm'),
    ], string='Loại phiếu', required=True, index=True, tracking=True,
        default=lambda self: self.env.context.get('default_estimate_type') or 'order',
        help="Phiếu tính giá chỉ để tính giá, không tạo đơn hàng.")
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('done', 'Đã chốt giá'),
        ('ordered', 'Đã tạo đơn hàng'),
        ('cancel', 'Đã hủy'),
    ], string='Trạng thái', default='draft', required=True, copy=False, tracking=True, index=True)
    partner_id = fields.Many2one('res.partner', string='Khách hàng', tracking=True, check_company=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty', required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Tiền tệ')
    user_id = fields.Many2one('res.users', string='Người lập', default=lambda self: self.env.user, tracking=True)
    date_estimate = fields.Date(string='Ngày dự toán', default=fields.Date.context_today, required=True)
    note = fields.Text(string='Ghi chú')
    line_ids = fields.One2many('sale.estimate.line', 'estimate_id', string='Sản phẩm yêu cầu', copy=True)
    sale_order_id = fields.Many2one('sale.order', string='Đơn bán hàng', copy=False, readonly=True, ondelete='set null')
    sale_order_state = fields.Selection(related='sale_order_id.state', string='Trạng thái đơn hàng')

    amount_cost = fields.Monetary(string='Tổng giá vốn', compute='_compute_amounts', store=True)
    amount_total = fields.Monetary(string='Tổng giá bán', compute='_compute_amounts', store=True, tracking=True)
    amount_margin = fields.Monetary(string='Lợi nhuận dự kiến', compute='_compute_amounts', store=True)
    usd_currency_id = fields.Many2one(related='company_id.estimate_usd_currency_id', string='Tiền tệ USD')
    amount_total_usd = fields.Monetary(
        string='Tổng giá bán (USD)', compute='_compute_amounts', store=True, currency_field='usd_currency_id')

    @api.depends('line_ids.subtotal_cost', 'line_ids.subtotal_price', 'date_estimate',
                 'company_id.estimate_usd_currency_id')
    def _compute_amounts(self):
        for estimate in self:
            estimate.amount_cost = sum(estimate.line_ids.mapped('subtotal_cost'))
            estimate.amount_total = sum(estimate.line_ids.mapped('subtotal_price'))
            estimate.amount_margin = estimate.amount_total - estimate.amount_cost
            estimate.amount_total_usd = self._convert_to_usd(
                estimate.amount_total, estimate.company_id, estimate.company_id.estimate_usd_currency_id,
                estimate.date_estimate)

    @api.model
    def _convert_to_usd(self, amount, company, usd, date):
        """Quy đổi theo tỷ giá Odoo. USD chưa bật hoặc chưa có tỷ giá thì trả 0, không báo lỗi."""
        if not amount or not company or not usd:
            return 0.0
        usd = usd.sudo()
        currency = company.currency_id
        if usd == currency:
            return amount
        if not usd.active:
            return 0.0
        # _convert dùng tỷ giá 1 khi chưa có tỷ giá nào, nên phải tự kiểm tra trước
        has_rate = self.env['res.currency.rate'].sudo().search_count([
            ('currency_id', '=', usd.id),
            ('company_id', 'in', (False, company.root_id.id)),
        ], limit=1)
        if not has_rate:
            return 0.0
        return currency._convert(amount, usd, company, date or fields.Date.context_today(self))

    @api.constrains('estimate_type', 'partner_id')
    def _check_partner_required(self):
        for estimate in self:
            if estimate.estimate_type == 'order' and not estimate.partner_id:
                raise ValidationError(_('Phiếu dự toán đơn hàng %s phải có khách hàng.', estimate.name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Mới')) == _('Mới'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.estimate') or _('Mới')
        return super().create(vals_list)

    def write(self, vals):
        if 'estimate_type' in vals and any(
                estimate.sale_order_id and estimate.estimate_type != vals['estimate_type'] for estimate in self):
            raise UserError(_('Không thể đổi loại phiếu khi phiếu đã có đơn bán hàng.'))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_without_order(self):
        if self.filtered('sale_order_id'):
            raise UserError(_('Không thể xóa phiếu dự toán đã có đơn bán hàng.'))

    def _get_mrp_company(self):
        return self.env['res.company'].sudo().search([('is_mrp', '=', True)], limit=1)

    def _check_can_create_order(self, mrp_company):
        self.ensure_one()
        if self.estimate_type != 'order':
            raise UserError(_('Phiếu tính giá không tạo được đơn hàng. Hãy chuyển thành dự toán đơn hàng trước.'))
        if self.state != 'draft':
            raise UserError(_('Chỉ tạo đơn hàng từ phiếu dự toán ở trạng thái nháp.'))
        if not self.company_id.is_service:
            raise UserError(_('Công ty %s chưa được đánh dấu là công ty thương mại.', self.company_id.name))
        if not mrp_company:
            raise UserError(_('Chưa cấu hình công ty sản xuất (Công ty sản xuất trên form công ty).'))
        if not self.company_id.sudo().estimate_route_ids:
            raise UserError(_('Công ty %s chưa cấu hình Tuyến cho sản phẩm dự toán.', self.company_id.name))
        if not self.line_ids:
            raise UserError(_('Phiếu dự toán chưa có sản phẩm.'))
        lines_without_bom = self.line_ids.filtered(lambda line: not line.bom_line_ids)
        if lines_without_bom:
            raise UserError(_('Các sản phẩm sau chưa có định mức nguyên vật liệu: %s',
                              ', '.join(lines_without_bom.mapped('name'))))
        operations_without_link = self.line_ids.operation_ids.filtered(
            lambda operation: not operation._get_mrp_workcenter(mrp_company))
        if operations_without_link:
            raise UserError(_('Các khu vực sau chưa có khu vực cùng mã ở công ty sản xuất: %s',
                              ', '.join(operations_without_link.workcenter_id.sudo().mapped('name'))))

    def action_create_sale_order(self):
        self.ensure_one()
        mrp_company = self._get_mrp_company()
        self._check_can_create_order(mrp_company)
        estimate = self.with_company(self.company_id)
        for index, line in enumerate(estimate.line_ids, start=1):
            line._create_or_update_product(index, mrp_company)
            line._create_bom(mrp_company)
        sale_order = self.env['sale.order'].with_company(self.company_id).create(estimate._prepare_sale_order_vals())
        self.write({'sale_order_id': sale_order.id, 'state': 'ordered'})
        return self.action_view_sale_order()

    def _prepare_sale_order_vals(self):
        self.ensure_one()
        return {
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'user_id': self.user_id.id,
            'origin': self.name,
            'estimate_id': self.id,
            'order_line': [fields.Command.create(line._prepare_sale_line_vals()) for line in self.line_ids],
        }

    def action_view_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Đơn bán hàng'),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
        }

    def _check_order_cancelled(self):
        if any(estimate.sale_order_id and estimate.sale_order_id.state != 'cancel' for estimate in self):
            raise UserError(_('Hãy hủy đơn bán hàng liên kết trước.'))

    def action_cancel(self):
        self._check_order_cancelled()
        self.write({'state': 'cancel'})

    def action_reset_draft(self):
        """Mở lại phiếu để sửa; lần tạo đơn sau dùng lại sản phẩm và thay BOM mới."""
        self._check_order_cancelled()
        self.write({'state': 'draft', 'sale_order_id': False})

    def action_done(self):
        """Chốt giá phiếu tính giá."""
        for estimate in self:
            if estimate.estimate_type != 'price':
                raise UserError(_('Chỉ phiếu tính giá mới chốt giá được.'))
            if estimate.state != 'draft':
                raise UserError(_('Chỉ chốt giá phiếu ở trạng thái nháp.'))
            if not estimate.line_ids:
                raise UserError(_('Phiếu tính giá chưa có sản phẩm.'))
        self.write({'state': 'done'})

    def action_convert_to_order(self):
        """Chép phiếu tính giá sang phiếu dự toán đơn hàng mới, phiếu gốc giữ nguyên để tra cứu."""
        self.ensure_one()
        if self.estimate_type != 'price' or self.state not in ('draft', 'done'):
            raise UserError(_('Chỉ chuyển phiếu tính giá ở trạng thái nháp hoặc đã chốt giá.'))
        if not self.partner_id:
            raise UserError(_('Hãy chọn khách hàng trên phiếu tính giá trước khi chuyển thành dự toán đơn hàng.'))
        new_estimate = self.copy({
            'estimate_type': 'order',
            'note': self.note,
        })
        self.message_post(body=_('Đã chuyển thành phiếu dự toán đơn hàng %s.', new_estimate._get_html_link()))
        new_estimate.message_post(body=_('Tạo từ phiếu tính giá %s.', self._get_html_link()))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phiếu dự toán'),
            'res_model': 'sale.estimate',
            'view_mode': 'form',
            'res_id': new_estimate.id,
            'context': {'default_estimate_type': 'order'},
        }


class SaleEstimateLine(models.Model):
    _name = 'sale.estimate.line'
    _description = 'Sản phẩm yêu cầu trên phiếu dự toán'
    _order = 'estimate_id, sequence, id'

    estimate_id = fields.Many2one(
        'sale.estimate', string='Phiếu dự toán', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    state = fields.Selection(related='estimate_id.state')
    company_id = fields.Many2one(related='estimate_id.company_id')
    currency_id = fields.Many2one(related='estimate_id.currency_id')

    # Thông tin yêu cầu của khách: chuyển sang sản phẩm mới và dòng đơn hàng
    name = fields.Char(string='Tên sản phẩm', required=True)
    categ_id = fields.Many2one(
        'product.category', string='Danh mục', required=True,
        default=lambda self: self.env.company.estimate_categ_id or self.env.ref(
            'product.product_category_goods', raise_if_not_found=False))
    uom_id = fields.Many2one(
        'uom.uom', string='Đơn vị', required=True, default=lambda self: self.env.ref('uom.product_uom_unit'))
    product_qty = fields.Float(string='Số lượng', required=True, default=1, digits='Product Unit')
    image_1920 = fields.Image(string='Hình ảnh', max_width=1920, max_height=1920)
    product_size = fields.Char(string='Số đo')
    note = fields.Text(string='Ghi chú')
    code_fabric = fields.Char(string='Mã vải')
    product_pattern_id = fields.Many2one('product.product', string='Mã họa tiết')
    note_pattern = fields.Text(string='Ghi chú họa tiết')

    bom_line_ids = fields.One2many('sale.estimate.bom.line', 'estimate_line_id', string='Định mức NVL', copy=True)
    operation_ids = fields.One2many('sale.estimate.operation', 'estimate_line_id', string='Hoạt động', copy=True)
    material_cost = fields.Monetary(string='Chi phí NVL', compute='_compute_cost', store=True)
    operation_cost = fields.Monetary(string='Chi phí hoạt động', compute='_compute_cost', store=True)
    extra_cost = fields.Monetary(string='Chi phí khác', help="Tính trên 1 đơn vị sản phẩm.")
    cost_unit = fields.Monetary(
        string='Giá vốn đơn vị', compute='_compute_cost', store=True, help="COST OF GOOD = NVL + hoạt động + chi phí khác.")

    # ---- Tham số tính giá: mặc định theo công ty, sửa được trên từng dòng ----
    studio_rate = fields.Float(string='Tỷ lệ studio', default=lambda self: self.env.company.estimate_studio_rate)
    profit_rate_lv1 = fields.Float(
        string='Tỷ lệ lợi nhuận LV1', default=lambda self: self.env.company.estimate_profit_rate_lv1)
    profit_rate_lv2 = fields.Float(
        string='Tỷ lệ lợi nhuận LV2', default=lambda self: self.env.company.estimate_profit_rate_lv2)
    markup_lv1_1 = fields.Float(string='Hệ số LV1 (1)', default=lambda self: self.env.company.estimate_markup_lv1_1)
    markup_lv1_2 = fields.Float(string='Hệ số LV1 (2)', default=lambda self: self.env.company.estimate_markup_lv1_2)
    markup_lv1_3 = fields.Float(string='Hệ số LV1 (3)', default=lambda self: self.env.company.estimate_markup_lv1_3)
    markup_lv2_1 = fields.Float(string='Hệ số LV2 (1)', default=lambda self: self.env.company.estimate_markup_lv2_1)
    markup_lv2_2 = fields.Float(string='Hệ số LV2 (2)', default=lambda self: self.env.company.estimate_markup_lv2_2)
    markup_lv2_3 = fields.Float(string='Hệ số LV2 (3)', default=lambda self: self.env.company.estimate_markup_lv2_3)
    price_rounding = fields.Monetary(
        string='Làm tròn giá chốt', default=lambda self: self.env.company.estimate_price_rounding)
    showroom_factor_1 = fields.Float(
        string='Hệ số mark up 1', default=lambda self: self.env.company.estimate_showroom_factor_1)
    showroom_factor_2 = fields.Float(
        string='Hệ số mark up 2', default=lambda self: self.env.company.estimate_showroom_factor_2)
    showroom_factor_3 = fields.Float(
        string='Hệ số mark up 2 (LV2)', default=lambda self: self.env.company.estimate_showroom_factor_3)
    wsp_rate = fields.Float(string='Tỷ lệ giá sỉ', default=lambda self: self.env.company.estimate_wsp_rate)
    ecom_rate = fields.Float(string='Tỷ lệ ecommerce', default=lambda self: self.env.company.estimate_ecom_rate)
    wsp2_rate = fields.Float(string='Tỷ lệ giá sỉ 2', default=lambda self: self.env.company.estimate_wsp2_rate)
    usd_currency_id = fields.Many2one(
        'res.currency', string='Tiền tệ USD', default=lambda self: self.env.company.estimate_usd_currency_id)

    # ---- AH..AR: giá thành và giá bán đề xuất ----
    studio_cost = fields.Monetary(string='Studio cost', compute='_compute_price_levels', store=True)
    profit_lv1 = fields.Monetary(string='Lợi nhuận LV1', compute='_compute_price_levels', store=True)
    profit_lv2 = fields.Monetary(string='Lợi nhuận LV2', compute='_compute_price_levels', store=True)
    total_cost_lv1 = fields.Monetary(string='Total cost LV1', compute='_compute_price_levels', store=True)
    total_cost_lv2 = fields.Monetary(string='Total cost LV2', compute='_compute_price_levels', store=True)
    price_lv1_1 = fields.Monetary(string='Giá LV1 (1)', compute='_compute_price_levels', store=True)
    price_lv1_2 = fields.Monetary(string='Giá LV1 (2)', compute='_compute_price_levels', store=True)
    price_lv1_3 = fields.Monetary(string='Giá LV1 (3)', compute='_compute_price_levels', store=True)
    price_lv2_1 = fields.Monetary(string='Giá LV2 (1)', compute='_compute_price_levels', store=True)
    price_lv2_2 = fields.Monetary(string='Giá LV2 (2)', compute='_compute_price_levels', store=True)
    price_lv2_3 = fields.Monetary(string='Giá LV2 (3)', compute='_compute_price_levels', store=True)

    # ---- AS..AU: bao bì, chỉ tham khảo, không cộng vào giá ----
    packaging_garment_bag = fields.Monetary(
        string='Garment bag', default=lambda self: self.env.company.estimate_packaging_garment_bag)
    packaging_price_tag = fields.Monetary(
        string='Price tag', default=lambda self: self.env.company.estimate_packaging_price_tag)
    packaging_box = fields.Monetary(
        string='Túi giấy / hộp', default=lambda self: self.env.company.estimate_packaging_box)
    packaging_total = fields.Monetary(
        string='Bao bì', compute='_compute_packaging_total', store=True, help="Chỉ tham khảo, không cộng vào giá.")

    # ---- AV..AY: giá chốt ----
    price_level = fields.Selection(
        [('lv1', 'LV1'), ('lv2', 'LV2')], string='Mức giá', default='lv2', required=True)
    price_option = fields.Selection(
        [('1', 'Hệ số 1'), ('2', 'Hệ số 2'), ('3', 'Hệ số 3')], string='Hệ số', default='1', required=True)
    price_factor_label = fields.Char(string='Hệ số đã chọn', compute='_compute_price_factor_label')
    suggested_price = fields.Monetary(string='Giá đề xuất', compute='_compute_suggested_price', store=True)
    price_unit = fields.Monetary(
        string='Giá chốt', compute='_compute_price_unit', store=True, readonly=False, copy=True,
        help="Giá đề xuất làm tròn theo cấu hình công ty, sửa tay được. Giá này đưa lên đơn bán hàng.")
    price_manual = fields.Boolean(string='Giá tự định', compute='_compute_price_manual')
    rrp_intl = fields.Monetary(string='RRP quốc tế')

    # ---- BA..BR: showroom, sỉ, ecommerce ----
    showroom_markup_1 = fields.Monetary(string='Mark up 1', compute='_compute_showroom_markup', store=True)
    showroom_markup_2 = fields.Monetary(string='Mark up 2', compute='_compute_showroom_markup', store=True)
    showroom_markup_3 = fields.Monetary(string='Mark up 2 (LV2)', compute='_compute_showroom_markup', store=True)
    rrp_showroom = fields.Monetary(
        string='RRP showroom', compute='_compute_rrp_showroom', store=True, readonly=False, copy=True,
        help="Mặc định = Mark up 2 làm tròn, sửa tay được.")
    wsp_price = fields.Monetary(string='Giá sỉ', compute='_compute_channel_prices', store=True)
    ecom_price = fields.Monetary(string='Giá ecommerce', compute='_compute_channel_prices', store=True)
    wsp2_price = fields.Monetary(string='Giá sỉ 2', compute='_compute_channel_prices', store=True)
    profit_ecom_pct = fields.Float(string='LN ecom', compute='_compute_channel_prices', store=True)
    profit_wsp_pct = fields.Float(string='LN sỉ', compute='_compute_channel_prices', store=True)
    compare_vn_pct = fields.Float(string='So với VN', compute='_compute_channel_prices', store=True)

    # ---- Quy đổi USD theo tỷ giá Odoo ----
    price_unit_usd = fields.Monetary(
        string='Giá chốt (USD)', compute='_compute_usd', store=True, currency_field='usd_currency_id')
    rrp_intl_usd = fields.Monetary(
        string='RRP quốc tế (USD)', compute='_compute_usd', store=True, currency_field='usd_currency_id')
    rrp_showroom_usd = fields.Monetary(
        string='RRP showroom (USD)', compute='_compute_usd', store=True, currency_field='usd_currency_id')
    wsp_price_usd = fields.Monetary(
        string='Giá sỉ (USD)', compute='_compute_usd', store=True, currency_field='usd_currency_id')
    ecom_price_usd = fields.Monetary(
        string='Giá ecommerce (USD)', compute='_compute_usd', store=True, currency_field='usd_currency_id')
    wsp2_price_usd = fields.Monetary(
        string='Giá sỉ 2 (USD)', compute='_compute_usd', store=True, currency_field='usd_currency_id')

    subtotal_cost = fields.Monetary(string='Tổng giá vốn', compute='_compute_subtotals', store=True)
    subtotal_price = fields.Monetary(string='Tổng giá bán', compute='_compute_subtotals', store=True)

    # Lọc trong bảng tính giá
    estimate_type = fields.Selection(related='estimate_id.estimate_type', store=True, string='Loại phiếu')
    partner_id = fields.Many2one(related='estimate_id.partner_id', store=True, string='Khách hàng')
    date_estimate = fields.Date(related='estimate_id.date_estimate', store=True, string='Ngày dự toán')

    product_id = fields.Many2one('product.product', string='Sản phẩm đã tạo', copy=False, readonly=True)
    bom_id = fields.Many2one('mrp.bom', string='BOM đã tạo', copy=False, readonly=True)

    @api.depends('bom_line_ids.subtotal', 'operation_ids.subtotal', 'extra_cost')
    def _compute_cost(self):
        for line in self:
            line.material_cost = sum(line.bom_line_ids.mapped('subtotal'))
            line.operation_cost = sum(line.operation_ids.mapped('subtotal'))
            line.cost_unit = line.material_cost + line.operation_cost + line.extra_cost

    @api.depends('cost_unit', 'studio_rate', 'profit_rate_lv1', 'profit_rate_lv2',
                 'markup_lv1_1', 'markup_lv1_2', 'markup_lv1_3', 'markup_lv2_1', 'markup_lv2_2', 'markup_lv2_3')
    def _compute_price_levels(self):
        """Cột AH..AR của sheet bespoke."""
        for line in self:
            line.studio_cost = line.cost_unit * line.studio_rate
            base = line.cost_unit + line.studio_cost
            line.profit_lv1 = base * line.profit_rate_lv1
            line.profit_lv2 = base * line.profit_rate_lv2
            line.total_cost_lv1 = base + line.profit_lv1
            line.total_cost_lv2 = base + line.profit_lv2
            for level in ('lv1', 'lv2'):
                for option in ('1', '2', '3'):
                    line[f'price_{level}_{option}'] = line[f'total_cost_{level}'] * line[f'markup_{level}_{option}']

    @api.depends('packaging_garment_bag', 'packaging_price_tag', 'packaging_box')
    def _compute_packaging_total(self):
        for line in self:
            line.packaging_total = line.packaging_garment_bag + line.packaging_price_tag + line.packaging_box

    @api.depends('price_level', 'price_option', 'price_lv1_1', 'price_lv1_2', 'price_lv1_3',
                 'price_lv2_1', 'price_lv2_2', 'price_lv2_3')
    def _compute_suggested_price(self):
        for line in self:
            level, option = line.price_level or 'lv2', line.price_option or '1'
            line.suggested_price = line[f'price_{level}_{option}']

    @api.depends('price_level', 'price_option', 'markup_lv1_1', 'markup_lv1_2', 'markup_lv1_3',
                 'markup_lv2_1', 'markup_lv2_2', 'markup_lv2_3')
    def _compute_price_factor_label(self):
        for line in self:
            factor = line[f'markup_{line.price_level or "lv2"}_{line.price_option or "1"}']
            line.price_factor_label = '× %s' % ('%g' % factor).replace('.', ',')

    def _round_price(self, amount):
        self.ensure_one()
        if self.price_rounding > 0:
            return float_round(amount, precision_rounding=self.price_rounding)
        return self.currency_id.round(amount) if self.currency_id else amount

    @api.depends('suggested_price', 'price_rounding')
    def _compute_price_unit(self):
        """Cột AV: giá đề xuất làm tròn (Excel: 10.506 -> 10.500)."""
        for line in self:
            line.price_unit = line._round_price(line.suggested_price)

    @api.depends('price_unit', 'suggested_price', 'price_rounding')
    def _compute_price_manual(self):
        for line in self:
            rounding = line.currency_id.rounding if line.currency_id else 0.01
            line.price_manual = float_compare(
                line.price_unit, line._round_price(line.suggested_price), precision_rounding=rounding) != 0

    @api.depends('price_unit', 'total_cost_lv2', 'showroom_factor_1', 'showroom_factor_2', 'showroom_factor_3')
    def _compute_showroom_markup(self):
        for line in self:
            line.showroom_markup_1 = line.price_unit * line.showroom_factor_1
            line.showroom_markup_2 = line.showroom_markup_1 * line.showroom_factor_2
            line.showroom_markup_3 = line.total_cost_lv2 * line.showroom_factor_3

    @api.depends('showroom_markup_2', 'price_rounding')
    def _compute_rrp_showroom(self):
        for line in self:
            line.rrp_showroom = line._round_price(line.showroom_markup_2)

    @api.depends('rrp_showroom', 'wsp_rate', 'ecom_rate', 'wsp2_rate', 'total_cost_lv1', 'price_unit')
    def _compute_channel_prices(self):
        def ratio(value, base):
            return (value - base) / base if base else 0.0

        for line in self:
            line.wsp_price = line.rrp_showroom * line.wsp_rate
            line.ecom_price = line.rrp_showroom * line.ecom_rate
            line.wsp2_price = line.rrp_showroom * line.wsp2_rate
            line.profit_ecom_pct = ratio(line.ecom_price, line.total_cost_lv1)
            line.profit_wsp_pct = ratio(line.wsp_price, line.total_cost_lv1)
            line.compare_vn_pct = ratio(line.rrp_showroom, line.price_unit)

    @api.depends('price_unit', 'rrp_intl', 'rrp_showroom', 'wsp_price', 'ecom_price', 'wsp2_price',
                 'usd_currency_id', 'estimate_id.date_estimate', 'estimate_id.company_id')
    def _compute_usd(self):
        Estimate = self.env['sale.estimate']
        for line in self:
            company = line.estimate_id.company_id or self.env.company
            date = line.estimate_id.date_estimate
            for field in ('price_unit', 'rrp_intl', 'rrp_showroom', 'wsp_price', 'ecom_price', 'wsp2_price'):
                line[f'{field}_usd'] = Estimate._convert_to_usd(line[field], company, line.usd_currency_id, date)

    @api.depends('product_qty', 'cost_unit', 'price_unit')
    def _compute_subtotals(self):
        for line in self:
            line.subtotal_cost = line.product_qty * line.cost_unit
            line.subtotal_price = line.product_qty * line.price_unit

    def action_open_estimate(self):
        """Bảng tính giá: bấm dòng mở phiếu cha."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phiếu dự toán'),
            'res_model': 'sale.estimate',
            'view_mode': 'form',
            'res_id': self.estimate_id.id,
            'context': {'default_estimate_type': self.estimate_type},
        }

    def _create_or_update_product(self, index, mrp_company):
        """Tạo sản phẩm dùng chung 2 công ty. Sudo vì nhân viên bán hàng không có quyền tạo sản phẩm."""
        self.ensure_one()
        estimate = self.estimate_id
        product_vals = {
            'name': self.name,
            'categ_id': self.categ_id.id,
            'uom_id': self.uom_id.id,
            'list_price': self.price_unit,
            'image_1920': self.image_1920,
            'code_fabric': self.code_fabric,
            'note': self.note,
            'route_ids': [fields.Command.set(estimate.company_id.sudo().estimate_route_ids.ids)],
        }
        if self.product_id:
            product = self.product_id.sudo()
            product.product_tmpl_id.write(product_vals)
            product.seller_ids.filtered(lambda seller: seller.company_id == estimate.company_id).unlink()
        else:
            product = self.env['product.product'].sudo().create({
                **product_vals,
                'type': 'consu',
                'is_storable': True,
                'sale_ok': True,
                'purchase_ok': True,
                'company_id': False,
                'default_code': '%s-%02d' % (estimate.name, index),
            })
            self.product_id = product
        # code_fabric/note khai báo riêng trên product.product nên phải ghi cả ở biến thể
        product.write({
            'code_fabric': self.code_fabric,
            'note': self.note,
            'seller_ids': [fields.Command.create({
                'partner_id': mrp_company.partner_id.id,
                'company_id': estimate.company_id.id,
                'currency_id': self.currency_id.id,
                'price': self.cost_unit,
                'min_qty': 0,
            })],
        })
        for company in estimate.company_id | mrp_company:
            product.with_company(company).standard_price = self.currency_id._convert(
                self.cost_unit, company.currency_id, company, estimate.date_estimate)

    def _create_bom(self, mrp_company):
        self.ensure_one()
        self.bom_id.sudo().active = False
        products = self.product_id
        picking_types = self.env['stock.picking.type'].sudo().search(
            [('code', '=', 'mrp_operation'), ('company_id', '=', mrp_company.id)])
        self.bom_id = self.env['mrp.bom'].sudo().with_company(mrp_company).create({
            'product_tmpl_id': self.product_id.product_tmpl_id.id,
            'product_qty': 1,
            'product_uom_id': self.uom_id.id,
            'type': 'normal',
            'company_id': mrp_company.id,
            'code': self.estimate_id.name,
            'bom_line_ids': [fields.Command.create({
                'product_id': bom_line.product_id.id,
                'product_qty': bom_line.product_qty,
                'product_uom_id': bom_line.product_uom_id.id,
            }) for bom_line in self.bom_line_ids],
            'operation_ids': [fields.Command.create({
                'name': operation.name,
                'workcenter_id': operation._get_mrp_workcenter(mrp_company).id,
                'sequence': operation.sequence,
                'cost_mode': operation.cost_mode,
                'time_mode': operation.time_mode,
                'time_mode_batch': operation.time_mode_batch,
                'time_cycle_manual': operation.time_cycle_manual,
                'employee_ratio': operation.employee_ratio,
                'quality_point_ids': [fields.Command.create(instruction._prepare_quality_point_vals(products, picking_types))
                                      for instruction in operation.instruction_ids],
            }) for operation in self.operation_ids],
        })

    def _prepare_sale_line_vals(self):
        self.ensure_one()
        product = self.product_id
        return {
            'product_id': product.id,
            'name': product.display_name,
            'product_uom_qty': self.product_qty,
            'product_uom_id': self.uom_id.id,
            'price_unit': self.price_unit,
            'default_code': product.default_code,
            'image_128': product.image_128,
            'product_size': self.product_size,
            'note': self.note,
            'code_fabric': self.code_fabric,
            'product_pattern_id': self.product_pattern_id.id,
            'product_pattern_image': self.product_pattern_id.image_128,
            'note_pattern': self.note_pattern,
        }


class SaleEstimateOperation(models.Model):
    _name = 'sale.estimate.operation'
    _description = 'Hoạt động trên phiếu dự toán'
    _order = 'estimate_line_id, sequence, id'

    estimate_line_id = fields.Many2one(
        'sale.estimate.line', string='Dòng dự toán', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    currency_id = fields.Many2one(related='estimate_line_id.currency_id')
    workcenter_id = fields.Many2one('mrp.workcenter', string='Khu vực sản xuất', required=True)
    name = fields.Char(
        string='Hoạt động', required=True, compute='_compute_name', store=True, readonly=False, precompute=True)
    company_id = fields.Many2one(related='estimate_line_id.company_id')
    cost_mode = fields.Selection([
        ('actual', 'Thời gian thực tế'),
        ('estimated', 'Thời gian lý thuyết'),
    ], string='Chi phí dựa trên', default='actual', required=True,
        help="Chuyển sang hoạt động của BOM, dùng khi tính chi phí sản xuất thực tế.")
    time_mode = fields.Selection([
        ('manual', 'Cố định'),
        ('auto', 'Tính toán'),
    ], string='Tính toán thời lượng', default='manual', required=True,
        help="Chuyển sang hoạt động của BOM. Dự toán luôn tính theo Thời lượng mặc định.")
    time_mode_batch = fields.Integer(string='Dựa trên', default=10)
    time_cycle_manual = fields.Float(string='Thời lượng/1 SP (phút)', default=60)
    employee_ratio = fields.Float(
        string='Khả năng nhân viên', default=1, help="Số nhân viên cần để hoàn thành hoạt động.")
    employee_costs_hour = fields.Monetary(
        string='Chi phí nhân công theo giờ', compute='_compute_costs_hour', store=True, readonly=False,
        help="Lấy theo khu vực cùng mã ở công ty sản xuất, tính cho 1 nhân viên, có thể sửa theo giá dự kiến.")
    instruction_ids = fields.One2many('sale.estimate.instruction', 'operation_id', string='Hướng dẫn', copy=True)
    costs_hour = fields.Monetary(
        string='Chi phí theo giờ', compute='_compute_costs_hour', store=True, readonly=False,
        help="Lấy theo khu vực cùng mã ở công ty sản xuất, có thể sửa theo giá dự kiến.")
    subtotal = fields.Monetary(string='Thành tiền', compute='_compute_subtotal', store=True)

    @api.depends('workcenter_id')
    def _compute_name(self):
        for operation in self:
            operation.name = operation.name or operation.workcenter_id.sudo().name

    def _get_mrp_workcenter(self, mrp_company):
        """Khu vực của công ty sản xuất có cùng mã với khu vực chọn trên phiếu."""
        self.ensure_one()
        code = self.workcenter_id.sudo().code
        if not code:
            return self.env['mrp.workcenter'].sudo()
        return self.env['mrp.workcenter'].sudo().search(
            [('company_id', '=', mrp_company.id), ('code', '=', code)], limit=1)

    @api.depends('workcenter_id')
    def _compute_costs_hour(self):
        mrp_company = self.env['sale.estimate']._get_mrp_company()
        for operation in self:
            workcenter = operation._get_mrp_workcenter(mrp_company)
            if not workcenter:
                operation.costs_hour = 0
                operation.employee_costs_hour = 0
                continue
            currency = operation.currency_id or workcenter.currency_id
            date = operation.estimate_line_id.estimate_id.date_estimate or fields.Date.context_today(self)
            operation.costs_hour = workcenter.currency_id._convert(
                workcenter.costs_hour, currency, workcenter.company_id, date)
            operation.employee_costs_hour = workcenter.currency_id._convert(
                workcenter.employee_costs_hour, currency, workcenter.company_id, date)

    @api.onchange('workcenter_id')
    def _onchange_workcenter_id_estimate_time(self):
        """Thời lượng mặc định lấy theo Thời gian dự kiến của khu vực cùng mã ở công ty sản xuất
        (giống chi phí theo giờ), không có thì lấy khu vực đang chọn. Cả hai bằng 0 thì giữ nguyên."""
        mrp_company = self.env['sale.estimate']._get_mrp_company()
        for operation in self.filtered('workcenter_id'):
            estimate_time = (operation._get_mrp_workcenter(mrp_company).estimate_time
                             or operation.workcenter_id.sudo().estimate_time)
            if estimate_time:
                operation.time_cycle_manual = estimate_time

    @api.depends('time_cycle_manual', 'costs_hour', 'employee_costs_hour', 'employee_ratio')
    def _compute_subtotal(self):
        """Cùng công thức với chi phí hoạt động của BOM trong mrp_workorder."""
        for operation in self:
            operation.subtotal = operation.time_cycle_manual / 60 * (
                operation.costs_hour + operation.employee_costs_hour * (operation.employee_ratio or 1))


class SaleEstimateInstruction(models.Model):
    _name = 'sale.estimate.instruction'
    _description = 'Hướng dẫn của hoạt động trên phiếu dự toán'
    _order = 'operation_id, sequence, id'

    operation_id = fields.Many2one(
        'sale.estimate.operation', string='Hoạt động', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    title = fields.Char(string='Tiêu đề', required=True)
    # Nhân viên bán hàng không có quyền đọc quality.point.test_type nên dùng selection theo technical_name
    test_type = fields.Selection([
        ('instructions', 'Hướng dẫn'),
        ('picture', 'Chụp ảnh'),
    ], string='Loại', default='instructions', required=True)
    note = fields.Html(string='Nội dung')

    def _prepare_quality_point_vals(self, products, picking_types):
        self.ensure_one()
        test_type = self.env['quality.point.test_type'].sudo().search([('technical_name', '=', self.test_type)], limit=1)
        return {
            'title': self.title,
            'sequence': self.sequence,
            'test_type_id': test_type.id,
            'note': self.note,
            'product_ids': [fields.Command.set(products.ids)],
            'picking_type_ids': [fields.Command.set(picking_types.ids)],
        }


class SaleEstimateBomLine(models.Model):
    _name = 'sale.estimate.bom.line'
    _description = 'Định mức NVL trên phiếu dự toán'
    _order = 'estimate_line_id, sequence, id'

    estimate_line_id = fields.Many2one(
        'sale.estimate.line', string='Dòng dự toán', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    currency_id = fields.Many2one(related='estimate_line_id.currency_id')
    # Chỉ NVL dùng chung: BOM nằm ở công ty sản xuất nên không chọn được NVL riêng của công ty thương mại
    product_id = fields.Many2one(
        'product.product', string='Nguyên vật liệu', required=True,
        domain=[('type', '=', 'consu'), ('company_id', '=', False)])
    product_qty = fields.Float(string='Định mức/1 SP', required=True, default=1, digits='Product Unit')
    product_uom_id = fields.Many2one(
        'uom.uom', string='Đơn vị', required=True,
        compute='_compute_product_uom_id', store=True, readonly=False, precompute=True)
    cost_unit = fields.Monetary(
        string='Đơn giá NVL', compute='_compute_cost_unit', store=True, readonly=False,
        help="Lấy theo giá vốn tại công ty sản xuất, có thể sửa theo giá dự kiến.")
    subtotal = fields.Monetary(string='Thành tiền', compute='_compute_subtotal', store=True)

    @api.depends('product_id')
    def _compute_product_uom_id(self):
        for line in self:
            line.product_uom_id = line.product_id.uom_id

    @api.depends('product_id', 'product_uom_id')
    def _compute_cost_unit(self):
        mrp_company = self.env['sale.estimate']._get_mrp_company()
        for line in self:
            if not line.product_id or not line.product_uom_id:
                line.cost_unit = 0
                continue
            estimate = line.estimate_line_id.estimate_id
            cost_company = mrp_company or estimate.company_id or self.env.company
            product = line.product_id.sudo().with_company(cost_company)
            cost = product.uom_id._compute_price(product.standard_price, line.product_uom_id)
            line.cost_unit = cost_company.currency_id._convert(
                cost, line.currency_id or cost_company.currency_id, cost_company,
                estimate.date_estimate or fields.Date.context_today(self))

    @api.depends('product_qty', 'cost_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.product_qty * line.cost_unit
