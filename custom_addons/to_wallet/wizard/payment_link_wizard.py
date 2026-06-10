from odoo import api, models, _


class PaymentLinkWizard(models.TransientModel):
    _inherit = 'payment.link.wizard'

    @api.onchange('amount', 'description')
    def _onchange_amount(self):
        res_model = self.res_model
        wallet_providers = self.env['payment.provider'].search([
            ('code', '=', 'wallet'),
            ('state', '=', 'enabled'),
            ('is_published', '=', True)
        ])
        if wallet_providers:
            proposed_amount = 0
            record = self.env[res_model].browse(self.res_id)
            if res_model == 'sale.order':
                invoices = record.invoice_ids.filtered(lambda x: x.state != 'cancel' and x.invoice_line_ids.sale_line_ids.order_id == record)
                proposed_amount = record.amount_total - sum(invoices.mapped('amount_total'))
            elif res_model == 'account.move':
                proposed_amount = record.amount_residual
            if self.currency_id.compare_amounts(proposed_amount, 0) > 0 and self.currency_id.compare_amounts(self.amount, proposed_amount) < 0:
                return {
                    'warning': {
                        'title': _("Feature not supported!"),
                        'message': _(
                            "Currently, when making an online payment with an e-wallet, the system doesn't allow partial payments. "
                            "Please make sure the total amount is set to %s to use the e-wallet payment method!"
                        ) % self.currency_id.format(proposed_amount),
                    },
                }
