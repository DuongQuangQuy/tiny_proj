from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.tools import groupby


class WalletPaymentWizard(models.TransientModel):
    _name = 'wallet.payment.wizard'
    _description = 'Wallet Payment Wizard'

    # def _default_journal_id(self):
    #     return self.env.company._get_automatic_entry_journal()

    payment_date = fields.Date(string='Payment Date', required=True, default=fields.Date.context_today)
    wallet_type_id = fields.Many2one('wallet.type', string='Wallet Type', required=True, check_company=True)
    journal_id = fields.Many2one('account.journal', string='Journal',
        domain="[('company_id', 'in', [company_id, False]), ('type', '=', 'general')]")
    move_line_ids = fields.Many2many('account.move.line', string='Journal Items', readonly=True, copy=False)
    account_type = fields.Selection(
        selection=[('asset_receivable', 'Receivable'), ('liability_payable', 'Payable')],
        required=True, string='Account Type'
    )
    company_id = fields.Many2one('res.company', string='Company')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if not set(fields_list) & set(['move_line_ids', 'company_id']):
            return res
        if self._context.get('active_model') == 'account.move':
            move_lines = self.env['account.move'].browse(self._context.get('active_ids', [])).line_ids
            move_lines = move_lines.filtered(lambda l: l.account_type in ['asset_receivable', 'liability_payable'])
        elif self._context.get('active_model') == 'account.move.line':
            move_lines = self.env['account.move.line'].browse(self._context.get('active_ids', []))
        else:
            raise UserError(_("The wallet payment register wizard should only be called on account.move or account.move.line records."))
        if not move_lines:
            raise UserError(_("You can't register a payment because there is nothing left to pay on the selected journal items."))
        if any(move.state != 'posted' for move in move_lines.move_id):
            raise UserError(_("You can only use this wizard for posted journal items."))
        if any(line.account_type not in ['asset_receivable', 'liability_payable'] for line in move_lines):
            raise UserError(_("You can only use this wizard on journal items that have account type Receivable or Payable!"))
        if len(set(move_lines.mapped('account_type'))) > 1:
            raise UserError(_("You can't register payments for both receivable and payable at the same time!"))
        if any(move_line.reconciled for move_line in move_lines):
            raise UserError(_("You cannot use this wizard for journal items that are not yet reconciled!"))
        if any(line.company_id.root_id != move_lines[0].company_id.root_id for line in move_lines):
            raise UserError(_("You cannot use this wizard on journal items belonging to different companies!"))
        if any(line.partner_id != move_lines[0].partner_id for line in move_lines):
            raise UserError(_("You cannot use this wizard on journal items belonging to different partners!"))
        company = move_lines.company_id.ensure_one()
        # journal = company._get_automatic_entry_journal()
        res.update({
            'company_id': company.id,
            'move_line_ids': [(6, 0, move_lines.ids)],
            # 'journal_id': journal.id,
            'account_type': move_lines[0].account_type,
        })
        return res

    def _transfer_payable_account_to_receivable_account(self, move_lines, transfer_amount, receivable_account):
        self.ensure_one()
        ctx = self._prepare_context_to_transfer_account(move_lines, transfer_amount, receivable_account)
        wizard = self.env['account.automatic.entry.wizard'].sudo().with_context(**ctx).create({
            'date': self.payment_date,
            'journal_id': self.journal_id or self.company_id._get_automatic_entry_journal().id,
        })
        action = wizard.do_action()
        move = self.env['account.move'].browse(action.get('res_id', 0)).exists()
        return move.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')

    def _prepare_context_to_transfer_account(self, move_lines, transfer_amount, destination_account):
        self.ensure_one()
        return {
            'active_model': 'account.move.line',
            'active_ids': move_lines.ids,
            'default_total_amount': transfer_amount,
            'default_destination_partner_id': move_lines.partner_id.ensure_one().id,
            'default_destination_account_id': destination_account.id,
            'default_action': 'change_account',
            'force_automatic_entry_wizard_total_amount': True,
        }

    def _prepare_params_to_create_wallet_history(self, move_lines, history_type):
        """
        Hook method. Allow extend value to create wallet history/.
        """
        self.ensure_one()
        return {
            'amount': self._get_payment_amount(move_lines),
            'history_type': history_type,
            'force_done': True,
            'account_move_line_ids': [(6, 0, move_lines.ids)]
        }

    def _process(self):
        """
        Match receivable/payable journal items to wallets. Do it in three stages:
        1. In the first stage we will group the journal entries by partner, currency, sign.
        2. In the second stage, we calculate the amount to be deducted/added to the wallet according to the values grouped
        in the first stage. For journal items with the 'Payable' account, we will change to the 'Receivable' account to
        switch the partner's role from 'Supplier' to 'Customer'. Additionally, during this phase we also determine journal
        items will be linked with the wallet history will create in next stage.
        3. In the third stage, we will create a wallet history from the data identified from previous stages. Once the wallet
        history is successfully created, it is necessary to update the wallet information for  journal items which linked
        to wallet history.
        :return: recordset wallet.history(...),
        """
        wallet_histories = self.env['wallet.history']
        for wizard in self:
            company = wizard.company_id
            company_currency = company.currency_id
            payment_date = wizard.payment_date
            # The first stage
            grouped_amls = {
                key: self.env['account.move.line'].concat(*value)
                for key, value in groupby(wizard.move_line_ids, lambda aml: (aml.partner_id, aml.currency_id, -1 if aml.debit > 0 else 1))
            }
            # The second stage
            for key, amls in grouped_amls.items():
                partner, currency, sign = key
                receivable_account = partner.property_account_receivable_id
                wallet = partner._create_wallet_if_not_exist(self.wallet_type_id, currency)
                amount = sign * abs(sum(amls.mapped('amount_residual_currency')))
                amls_todo = self.env['account.move.line']
                if sign > 0:  # sign > 0 means the credit of journal items is greater than 0
                    history_type = 'top-up'
                    if wizard.account_type == 'liability_payable':
                        transfer_amount = currency._convert(amount, company_currency, company, payment_date)
                        transfer_aml = wizard._transfer_payable_account_to_receivable_account(amls, transfer_amount, receivable_account)
                        amls_todo = transfer_aml
                    else:
                        amls_todo = amls
                else:
                    history_type = 'payment'
                    wallet_balance = wallet.amount
                    if currency.compare_amounts(wallet_balance, abs(amount)) < 0:
                        raise UserError(_("Wallet balance is not available! (Balance: %s)") % (currency.format(wallet_balance)))
                    if wizard.account_type == 'liability_payable':
                        transfer_amount = currency._convert(amount, company_currency, company, payment_date)
                        transfer_aml = wizard._transfer_payable_account_to_receivable_account(amls, transfer_amount, receivable_account)
                        amls_todo = transfer_aml
                    else:
                        amls_todo = amls
                # The third stage
                wallet_history = wallet._create_wallet_history(
                    amount=amount,
                    history_type=history_type,
                    force_done=True,
                    account_move_line_ids=[(6, 0, amls_todo.ids)]
                )
                if sign > 0:
                    for aml in amls_todo:
                        aml.update({'wallet_id': wallet.id, 'wallet_amount_currency': aml.amount_residual_currency})
                else:
                    wallet.with_context(
                        skip_creating_wallet_history={aml.id: [wallet_history.id] for aml in amls_todo}
                    )._reconcile_wallet(amls_todo)
                wallet_histories |= wallet_history
        return wallet_histories

    def acction_process(self):
        self.ensure_one()
        wallet_histories = self._process()
        action = self.env['ir.actions.act_window']._for_xml_id('to_wallet.action_view_wallet_histories')
        if len(wallet_histories) != 1:
            action['domain'] = [('id', 'in', wallet_histories.ids)]
        else:
            res = self.env.ref('to_wallet.wallet_history_form', False)
            action['views'] = [(res and res.id or False, 'form')]
            action['res_id'] = wallet_histories.id
        return action
