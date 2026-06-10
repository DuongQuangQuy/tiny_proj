from odoo import api, SUPERUSER_ID


def migrate(cr, installed_version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    wallet_payments = env['account.payment'].search([('wallet', '=', True)])
    for payment in wallet_payments:
        payment.wallet_amount = payment.amount

    move_lines = env['account.move.line'].search([('payment_id.wallet', '=', True), ('account_id.internal_type', '=', 'receivable')])
    for line in move_lines:
        vals = line.payment_id._get_wallet_move_line_vals()
        line.write(vals)
        line.matched_debit_ids.write({
            'wallet': True
        })
