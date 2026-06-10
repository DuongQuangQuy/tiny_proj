from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    loyalty_expense_account_id = fields.Many2one(related='company_id.loyalty_expense_account_id', readonly=False)
    loyalty_income_account_id = fields.Many2one(related='company_id.loyalty_income_account_id', readonly=False)
