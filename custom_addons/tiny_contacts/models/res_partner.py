from datetime import date

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"
    _rec_names_search = ['complete_name', 'code', 'code_old', 'email', 'ref', 'vat', 'company_registry']

    code = fields.Char(
        string='Code',
        copy=False,
        index=True,
    )
    code_old = fields.Char(
        string='Old Code',
    )
    birthday = fields.Date(
        string='Date of Birth'
    )
    partner_referral_id = fields.Many2one(
        'res.partner',
        string='Referrer'
    )

    note_size = fields.Text(string='Measurement Notes')
    note_supplier = fields.Text(string='Vendor Notes')

    partner_type = fields.Selection(
        selection=[
            ('supplier', 'Vendor'),
            ('pre_customer', 'Prospect'),
            ('customer', 'Customer'),
        ],
        string='Partner Type',
        default='pre_customer',
    )
    social = fields.Char(string='Social')
    personal_contact = fields.Char(string='Contact Person')

    def _ensure_partner_sequence_range(self):
        """Tạo date range cho năm hiện tại nếu chưa tồn tại"""

        seq = self.env.ref("tiny_contacts.seq_code_partner")

        today = fields.Date.today()
        year = today.year

        date_range = self.env["ir.sequence.date_range"].search([
            ("sequence_id", "=", seq.id),
            ("date_from", "<=", today),
            ("date_to", ">=", today),
        ], limit=1)

        if not date_range:
            self.env["ir.sequence.date_range"].create({
                "sequence_id": seq.id,
                "date_from": date(year, 1, 1),
                "date_to": date(year, 12, 31),
                "number_next": 1,
            })

        return seq

    def _generate_partner_code(self):
        self.ensure_one()

        self._ensure_partner_sequence_range()

        sequence = self.env["ir.sequence"].next_by_code(
            "res.partner.code"
        ) or "0001"

        name = (self.name or "").strip()

        if name:
            last_word = name.split()[-1]
            first_char = last_word[0].upper()
        else:
            first_char = "X"

        year = fields.Date.today().strftime("%y")

        return f"{first_char}-{year}-{sequence}"

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)

        for partner in partners:
            if not partner.code and partner.partner_type == 'customer':
                partner.code = partner._generate_partner_code()

        return partners

    def action_set_customer(self):
        for partner in self:
            if partner.partner_type != 'pre_customer':
                continue

            partner.partner_type = 'customer'

            if not partner.code:
                partner.code = partner._generate_partner_code()