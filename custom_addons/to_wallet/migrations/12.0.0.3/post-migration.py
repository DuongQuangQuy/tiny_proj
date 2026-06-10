from odoo import api, SUPERUSER_ID


def migrate(cr, installed_version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    wallets = env['wallet'].search([])
    wallets._compute_amount()
