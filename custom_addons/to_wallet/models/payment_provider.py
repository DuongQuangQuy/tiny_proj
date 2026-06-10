from odoo import api, fields, models


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('wallet', 'Wallet')], ondelete={'wallet': 'set default'})

    @api.depends('code')
    def _compute_view_configuration_fields(self):
        """ Override of payment to hide the credentials page. """
        super()._compute_view_configuration_fields()
        self.filtered(lambda p: p.code == 'wallet').show_credentials_page = False

    @api.model
    def _get_compatible_providers(
        self, company_id, partner_id, amount, currency_id=None, force_tokenization=False,
        is_express_checkout=False, is_validation=False, **kwargs
    ):
        compatible_providers = super(PaymentProvider, self)._get_compatible_providers(
            company_id=company_id, partner_id=partner_id, amount=amount, currency_id=currency_id,
            force_tokenization=force_tokenization, is_express_checkout=is_express_checkout,
            is_validation=is_validation, **kwargs
        )
        wallet_provider = compatible_providers.filtered(lambda p: p.code == 'wallet')
        if wallet_provider:
            partner = self.env['res.partner'].browse(partner_id).exists()
            currency = self.env['res.currency'].browse(currency_id).exists()
            # TODO: Improvements that allow partial payments when using online payment methods using e-wallets
            proposed_amount = 0
            if kwargs.get('invoice_id', False):
                invoice = self.env['account.move'].browse(kwargs['invoice_id'])
                proposed_amount = invoice.amount_residual
            elif kwargs.get('sale_order_id', False):
                sale_order = self.env['sale.order'].browse(kwargs['sale_order_id'])
                invoices = sale_order.invoice_ids.filtered(lambda x: x.state != 'cancel' and x.invoice_line_ids.sale_line_ids.order_id == sale_order)
                proposed_amount = sale_order.amount_total - sum(invoices.mapped('amount_total'))
            compatible_wallets = partner._get_wallets_pay_online(amount, currency)
            is_user_public = self.env.user._is_public()
            if not compatible_wallets or kwargs.get('exclude_wallet_provider', False) or \
                is_user_public or (not is_user_public and self.env.user.partner_id.id != partner_id) or \
                (currency.compare_amounts(proposed_amount, 0) > 0 and currency.compare_amounts(amount, proposed_amount) < 0):
                compatible_providers -= wallet_provider
        return compatible_providers

    @api.model
    def _get_wallets_pay_online(self, partner_id, amount, currency):
        wallets = self.env['wallet']
        partner = self.env['res.partner'].browse(partner_id).exists()
        if self.code != 'wallet' or not partner:
            return wallets
        return partner._get_wallets_pay_online(amount, currency)
