from odoo import models, fields


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    is_wallet = fields.Boolean(
        string='Transfer To Wallet',
        help="Check this field if you want to top up payment's residual amount after reconciling it with invoice."
    )
    wallet_type_id = fields.Many2one(comodel_name='wallet.type', string='Wallet Type')

    def _create_payment_vals_from_wizard(self, batch_result):
        res = super(AccountPaymentRegister, self)._create_payment_vals_from_wizard(batch_result)
        to_full_reconcile_amount = self._get_total_amount_in_wizard_currency_to_full_reconcile(batch_result)[0]
        wallet_amount = self.amount - to_full_reconcile_amount
        if self.is_wallet and self.payment_difference_handling == 'open' and self.currency_id.compare_amounts(wallet_amount, 0.0) > 0:
            res.update({
                'is_wallet': self.is_wallet,
                'wallet_amount': wallet_amount,
                'wallet_type_id': self.wallet_type_id.id
            })
        return res

    def _create_payments(self):
        """
        Add context to pass using wallet amount paying invoices
        """
        is_transfer_residual = self.is_wallet and self.payment_difference_handling == 'open'
        return super(AccountPaymentRegister, self.with_context(payment_residual_as_top_up=is_transfer_residual))._create_payments()
