from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    loyalty_expense_account_id = fields.Many2one('account.account', string='Sale Promotion Expense Account',
        help="An account to record expensed amount due to Sale promotion. It is usually an Expense account.")
    loyalty_income_account_id = fields.Many2one('account.account', string='Sale Promotion Income Account',
        help="An account to record gained amount due to Sale promotion. It is usually an Other Income account.")
