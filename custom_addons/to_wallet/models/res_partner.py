from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    wallet_ids = fields.One2many(
        'wallet', 'partner_id',
        groups="to_wallet.group_wallet_manager")
    commercial_partner_wallet_ids = fields.Many2many(
        'wallet',
        string='Commercial Partner Wallets',
        compute='_compute_commercial_partner_wallets',
        groups="to_wallet.group_wallet_manager"
        )
    wallets_count = fields.Integer(
        string='Wallets Count',
        compute='_compute_commercial_partner_wallets',
        groups="to_wallet.group_wallet_manager"
        )

    @api.depends('commercial_partner_id.wallet_ids', 'commercial_partner_id.child_ids.wallet_ids')
    def _compute_commercial_partner_wallets(self):
        wallets = self.env['wallet'].search(
            [('partner_id.commercial_partner_id', 'in', self.commercial_partner_id.ids)]
            )
        for r in self:
            r.commercial_partner_wallet_ids = wallets.filtered(
                lambda w: w.partner_id.commercial_partner_id == r.commercial_partner_id
                )
            r.wallets_count = len(r.commercial_partner_wallet_ids)

    def action_view_wallets(self):
        action = self.env['ir.actions.act_window']._for_xml_id('to_wallet.action_view_wallets')
        action['context'] = {}
        wallets_count = sum(self.mapped('wallets_count'))
        if wallets_count > 1:
            action['domain'] = [('partner_id.commercial_partner_id', 'in', self.commercial_partner_id.ids)]
        elif wallets_count == 1:
            res = self.env.ref('to_wallet.wallet_form', False)
            action['views'] = [(res and res.id or False, 'form')]
            action['res_id'] = self.commercial_partner_wallet_ids.id
        return action

    def _parepare_wallet_data(self, wallet_type, currency=None):
        self.ensure_one()
        currency = currency or self.currency_id or self.env.company.currency_id
        return {
            'currency_id': currency.id,
            'partner_id': self.commercial_partner_id.id,
            'wallet_type_id': wallet_type.id
        }

    def _create_wallet_if_not_exist(self, wallet_type, currency=None):
        """
        Method to create a partner's wallet in the given currency if not exists.

        :param currency: currency record for which the wallet will be generated.
            If no currency is passed, either the partner's currency or the company's currency will be applied
        :return: return the newly created wallet or the existing one if it exists.
        """
        self.ensure_one()
        currency = currency or self.currency_id or self.env.company.currency_id
        company = self.env.company
        wallet = self.commercial_partner_id.wallet_ids.filtered(
            lambda w: w.currency_id == currency and w.company_id == company and w.wallet_type_id == wallet_type
        )[:1]
        if not wallet:
            wallet = self.env['wallet'].sudo().create(self._parepare_wallet_data(wallet_type, currency))
        return wallet

    def _get_wallets_pay_online(self, amount, currency):
        self.ensure_one()
        return self.commercial_partner_wallet_ids.filtered(
            lambda w: w.wallet_type_id.allow_pay_online and w.currency_id == currency
            and currency.compare_amounts(w.amount, amount) >= 0
        )
