from odoo import fields, models


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    daily_reset = fields.Boolean(
        string='Reset Daily',
        help='When used with "Use subsequences per date_range", each day is a separate range and the number restarts from 1.')

    def _create_date_range_seq(self, date):
        if not self.daily_reset:
            return super()._create_date_range_seq(date)
        day = fields.Date.to_date(date)
        return self.env['ir.sequence.date_range'].sudo().create({
            'date_from': day,
            'date_to': day,
            'sequence_id': self.id,
        })
