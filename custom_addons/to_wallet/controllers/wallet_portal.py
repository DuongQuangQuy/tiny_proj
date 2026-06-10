import urllib.parse
import werkzeug
from operator import itemgetter
from odoo import SUPERUSER_ID, _
from odoo.exceptions import ValidationError, AccessError, MissingError
from odoo.http import request, route
from odoo.tools import groupby as groupby_element
from odoo.fields import Domain
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.addons.payment.controllers.portal import PaymentPortal
from odoo.addons.payment import utils as payment_utils


class WalletPortal(CustomerPortal):

    @staticmethod
    def _partner_sudo():
        return request.env.user.partner_id.sudo()

    def _partner_wallets(self):
        return self._partner_sudo().commercial_partner_id.wallet_ids

    def _prepare_home_portal_values(self, counters):
        value = super(WalletPortal, self)._prepare_home_portal_values(counters)
        if 'wallet_count' in counters:
            value['wallet_count'] = len(self._partner_wallets())
        return value

    # ------------------------------------------------------------
    # My Wallets
    # ------------------------------------------------------------

    def _get_wallet_domain(self):
        partner = self._partner_sudo()
        return [
            ('partner_id', '=', partner.commercial_partner_id.id)
        ]

    def _get_wallet_searchbar_sortings(self):
        return {
            'available_balance': {'label': _('Available Balance'), 'order': 'amount desc'},
            'pending_balance': {'label': _('Pending Balance'), 'order': 'amount_pending desc'},
            'currency': {'label': _('Currency'), 'order': 'currency_id'},
        }

    def _get_wallet_searchbar_filters(self):
        return {
            'all': {'label': _('All'), 'domain': []},
        }

    def _get_wallet_searchbar_groupby(self):
        return {
            'none': {'input': 'none', 'label': _('None')},
            'wallet_type': {'input': 'wallet_type_id', 'label': _('Wallet Type')},
            'currency': {'input': 'currency_id', 'label': _('Currency')},
        }

    @route('/my/wallets', type='http', auth="user", website=True)
    def portal_my_wallets(self, page=1, sortby='available_balance', filterby='all', groupby='wallet_type', **kw):
        values = self._prepare_my_wallets_values(page, sortby, filterby, groupby)
        return request.render('to_wallet.portal_wallets_page', values)

    def _prepare_my_wallets_values(self, page, sortby, filterby, groupby):
        values = self._prepare_portal_layout_values()
        Wallet = request.env['wallet']
        domain = self._get_wallet_domain()

        searchbar_sortings = self._get_wallet_searchbar_sortings()
        order = searchbar_sortings[sortby]['order']

        searchbar_filters = self._get_wallet_searchbar_filters()
        domain += searchbar_filters[filterby]['domain']

        searchbar_groupby = self._get_wallet_searchbar_groupby()

        wallets_count = Wallet.search_count(domain)
        pager = portal_pager(
            url="/my/wallets/",
            url_args={'sortby': sortby, 'filterby': filterby},
            total=wallets_count,
            page=page,
            step=self._items_per_page
        )

        wallets = Wallet.search(domain, order=order, limit=self._items_per_page, offset=(page - 1) * self._items_per_page)
        request.session['my_wallet_history'] = wallets.ids[:100]
        if groupby and groupby != 'none':
            grouped_wallets = [Wallet.concat(*g) for _, g in groupby_element(wallets, itemgetter(searchbar_groupby[groupby]['input']))]
        else:
            grouped_wallets = [wallets]

        values.update({
            'wallets': wallets,
            'page_name': 'wallet',
            'default_url': '/my/wallets',
            'pager': pager,
            'grouped_wallets': grouped_wallets,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_groupby': searchbar_groupby,
            'searchbar_filters': searchbar_filters,
            'sortby': sortby,
            'filterby': filterby,
            'groupby': groupby,
        })
        return values

    # ------------------------------------------------------------
    # My Wallet Histories
    # ------------------------------------------------------------

    def _get_wallet_history_domain(self, wallet):
        return [
            ('wallet_id', '=', wallet.id)
        ]

    def _get_wallet_history_searchbar_inputs(self):
        return {
            'all': {'input': 'all', 'label': _("Search All")},
            'code': {'input': 'code', 'label': _("Search Transaction Code")},
            'reference': {'input': 'reference', 'label': _("Search Transaction Reference")},
        }

    def _get_wallet_history_searchbar_sortings(self):
        return {
            'create_date': {'label': _("Newest"), 'order': 'create_date desc'},
            'amount': {'label': _("Amount"), 'order': 'amount desc'},
        }

    def _get_wallet_history_searchbar_filters(self):
        return {
            'all': {'label': _("All"), 'domain': []},
            'top-up': {'label': _("Top-Up Transaction"), 'domain': [('wallet_history_type', '=', 'top-up')]},
            'withdrawal': {'label': _("Withdrawal Transaction"), 'domain': [('wallet_history_type', '=', 'withdraw')]},
            'payment': {'label': _("Payment Transaction"), 'domain': [('wallet_history_type', '=', 'payment')]},
            'refund': {'label': _("Refund Transaction"), 'domain': [('wallet_history_type', '=', 'refund')]},
            'pending_state': {'label': _("Pending Status"), 'domain': [('state', '=', 'pending')]},
            'done_state': {'label': _("Successful Status"), 'domain': [('state', '=', 'done')]},
            'cancel_state': {'label': _("Cancelled Status"), 'domain': [('state', '=', 'cancel')]},
        }

    def _get_wallet_history_searchbar_groupby(self):
        return {
            'none': {'input': 'none', 'label': _("None")},
            'type': {'input': lambda h: h.wallet_history_type, 'label': _("Transaction Type")},
            'state': {'input': lambda h: h.state, 'label': _("Transaction Status")},
            'day': {'input': lambda h: h.create_date.day, 'label': _("Transaction Date: Day")},
            'month': {'input': lambda h: h.create_date.month, 'label': _("Transaction Date: Month")},
            'year': {'input': lambda h: h.create_date.year, 'label': _("Transaction Date: Year")},
        }



    def _get_wallet_history_search_domain(self, search_in, search):
        domain = Domain()

        if search_in in ('code', 'all'):
            domain |= Domain('name', 'ilike', search)

        if search_in in ('reference', 'all'):
            domain |= Domain('reference', 'ilike', search)

        return domain

    def _prepare_my_wallets_history_values(self, wallet, page, **kw):
        values = self._prepare_portal_layout_values()
        domain = self._get_wallet_history_domain(wallet)

        search = kw.get('search', None)
        search_in = kw.get('search_in', 'all')
        searchbar_inputs = self._get_wallet_history_searchbar_inputs()
        if search and search_in:
            domain += self._get_wallet_history_search_domain(search_in, search)

        sortby = kw.get('sortby', 'create_date')
        searchbar_sortings = self._get_wallet_history_searchbar_sortings()
        order = searchbar_sortings[sortby]['order']

        filterby = kw.get('filterby', 'all')
        searchbar_filters = self._get_wallet_history_searchbar_filters()
        if filterby:
            domain += searchbar_filters[filterby]['domain']

        groupby = kw.get('groupby', 'none')
        searchbar_groupby = self._get_wallet_history_searchbar_groupby()

        wallet_histories_count = request.env['wallet.history'].search_count(domain)
        pager = portal_pager(
            url=f'/my/wallets/transaction-history/{wallet.id}',
            url_args={'sortby': sortby, 'filterby': filterby},
            total=wallet_histories_count,
            page=page,
            step=self._items_per_page
        )

        wallet_histories = request.env['wallet.history'].search(domain, order=order, limit=self._items_per_page, offset=(page - 1) * self._items_per_page)
        request.session['my_wallet_transaction_history'] = wallet_histories.ids[:100]
        if groupby and groupby != 'none':
            grouped_wallet_histories = [request.env['wallet.history'].concat(*g) for _, g in groupby_element(wallet_histories, searchbar_groupby[groupby]['input'])]
        else:
            grouped_wallet_histories = [wallet_histories]

        values.update({
            'wallet': wallet,
            'wallet_histories': wallet_histories,
            'page_name': 'wallet_transaction_history',
            'default_url': f'/my/wallets/transaction-history/{wallet.id}',
            'pager': pager,
            'grouped_wallet_histories': grouped_wallet_histories,
            'searchbar_inputs': searchbar_inputs,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_groupby': searchbar_groupby,
            'searchbar_filters': searchbar_filters,
            'search_in': search_in,
            'sortby': sortby,
            'filterby': filterby,
            'groupby': groupby,
        })
        return values

    @route(['/my/wallets/transaction-history/<int:wallet_id>'], type='http', auth='user', website=True)
    def portal_my_wallet_history(self, wallet_id, access_token=None, page=1, **kw):
        if not wallet_id:
            raise werkzeug.exceptions.NotFound()
        try:
            wallet_sudo = self._document_check_access('wallet', int(wallet_id), access_token)
        except (AccessError, MissingError):
            raise werkzeug.exceptions.NotFound()
        values = self._prepare_my_wallets_history_values(wallet_sudo, page, **kw)
        return request.render('to_wallet.portal_wallet_histories_page', values)

    def _prepage_wallet_payment_withdraw_values(self, wallet, reference, amount, **kw):
        return {
            'amount': amount,
            'is_wallet': True,
            'wallet_amount': amount,
            'wallet_type_id': wallet.wallet_type_id.id,
            'payment_type': 'outbound',
            'currency_id': wallet.currency_id.id,
            'partner_id': wallet.partner_id.commercial_partner_id.id,
            'partner_type': 'customer',
            'company_id': wallet.company_id.id,
            'ref': reference,
        }

    def _create_wallet_withdraw_payment(self, wallet, reference, amount, **kw):
        payment_exists = request.env['account.payment'].sudo().search([('ref', '=', reference)], limit=1)
        if payment_exists:
            raise ValidationError(_("Withdrawal request with reference %s already exists.") % reference)
        payment_vals = self._prepage_wallet_payment_withdraw_values(wallet, reference, amount, **kw)
        AccountPayment = request.env['account.payment'].with_context(wallet_withdraw_from_portal=True)
        payment = AccountPayment.with_user(SUPERUSER_ID).with_company(request.env.company).create(payment_vals)
        receivable_line = payment.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        wallet._create_wallet_history(
            amount=-1 * abs(amount),
            history_type='withdraw',
            account_move_line_ids=[(6, 0, receivable_line.ids)]
        )
        return payment

    def _prepare_context_render_wallet_withdraw_payment_confirm(self, wallet, reference, amount, **kwarg):
        return {
            'wallet': wallet,
            'payment_reference': reference,
            'amount': amount,
        }

    @route('/my/wallets/withdraw', type='http', methods=['GET'], auth='user', website=True, sitemap=False)
    def wallet_withdraw_payment(self, reference, amount, wallet_id, access_token, **kwarg):
        # Cast numeric parameters as int or float and void them if their str value is malformed.
        amount = self._cast_as_float(amount)
        wallet_id = self._cast_as_int(wallet_id)

        # Raises HTTP 404 if the specified wallet is not found
        if not wallet_id:
            raise werkzeug.exceptions.NotFound()  # Must have specified wallet.

        wallet = request.env['wallet'].sudo().browse(PaymentPortal._cast_as_int(wallet_id)).exists()
        # Raise an HTTP 404 if a partner is provided with an invalid access token
        if not payment_utils.check_access_token(access_token, wallet.partner_id.id, amount, wallet.currency_id.id):
            raise werkzeug.exceptions.NotFound()  # Don't leak information about ids.

        user_sudo = request.env.user
        partner_sudo = user_sudo.partner_id
        logged_in = not user_sudo._is_public()
        if logged_in:
            # Raises HTTP 404 if the user has a different partner than the one on the wallet.
            if wallet.partner_id.id != partner_sudo.id:
                raise werkzeug.exceptions.NotFound()
        else:
            return request.redirect(
                # Escape special characters to avoid loosing original params when redirected
                f'/web/login?redirect={urllib.parse.quote(request.httprequest.full_path)}'
            )

        self._create_wallet_withdraw_payment(wallet, reference, amount, **kwarg)
        rendering_context = self._prepare_context_render_wallet_withdraw_payment_confirm(wallet, reference, amount, **kwarg)
        return request.render('to_wallet.wallet_withdraw_payment_confirm', rendering_context)

    @route('/my/wallets/initialization-data', type='jsonrpc', auth='user', website=True, sitemap=False)
    def fetch_wallet_creation_data(self, **kw):
        company = request.env.company
        currencies = request.env['res.currency'].search([])
        wallet_types = request.env['wallet.type'].search([
            ('company_id', 'in', [False, company.id]),
            '|', ('allow_top_up', '=', True),
            ('allow_withdraw', '=', True),
        ])
        return {
            'wallet_types': wallet_types.read(['id', 'name']),
            'currencies': currencies.read(['id', 'name'])
        }

    @route('/my/wallets/create', type='jsonrpc', auth='user', website=True, sitemap=False)
    def create_wallet(self, **post):
        partner = request.env.user.partner_id
        wallet_type_id = PaymentPortal._cast_as_int(post.get('wallet_type_id', False))
        currency_id = PaymentPortal._cast_as_int(post.get('currency_id', False))
        wallet_exists = partner.commercial_partner_id.wallet_ids.filtered(
            lambda w: w.currency_id.id == currency_id and w.wallet_type_id.id == wallet_type_id
        )

        if wallet_exists:
            raise ValidationError(_(
                "A wallet with currency %s already exists. Currency is unique for each wallet type!"
            ) % (wallet_exists.currency_id.name))

        try:
            # The except clause below should not let what has been done inside
            # here be committed. It should not either roll back everything in
            # this controller method. Instead, we use a savepoint to roll back
            # what has been done inside the try clause.
            with request.env.cr.savepoint():
                request.env['wallet'].with_user(SUPERUSER_ID).create({
                    'partner_id': partner.commercial_partner_id.id,
                    'currency_id': currency_id,
                    'wallet_type_id': wallet_type_id,
                })
                return {'success': True}
        except Exception as e:
            return {'error': str(e)}
