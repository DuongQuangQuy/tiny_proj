from odoo import api, SUPERUSER_ID


def migrate(cr, installed_version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    wallets = env['wallet'].search([])
    wallet_move_lines = wallets.mapped('move_line_ids.payment_id.move_line_ids.wallet_id.move_line_ids')
    wallet_move_lines._compute_wallet_amount_residual()
    wallets._compute_amount()
