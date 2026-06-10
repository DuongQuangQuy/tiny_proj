from odoo import api, SUPERUSER_ID


def migrate(cr, installed_version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    _sql = """
    SELECT id FROM account_move_line
    WHERE wallet_amount_currency != wallet_amount AND
          currency_id = company_currency_id AND
          wallet = true
    """
    cr.execute(_sql)
    line_ids = [line['id'] for line in cr.dictfetchall()]
    if line_ids:
        lines = env['account.move.line'].browse(line_ids)
        lines.read(['wallet_amount'])
        for line in lines:
            line.wallet_amount_currency = line.wallet_amount
