/** @odoo-module */


import publicWidget from '@web/legacy/js/public/public_widget';
import {_t} from "@web/core/l10n/translation";
import {PortalHomeCounters} from "@portal/js/portal";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {renderToString} from "@web/core/utils/render";
import {markup} from "@odoo/owl";
import {jsonrpc} from "@web/core/network/rpc_service";


PortalHomeCounters.include({
    /**
     * @override
     */
    _getCountersAlwaysDisplayed() {
        return this._super(...arguments).concat(['wallet_count']);
    },
});

publicWidget.registry.PortalWallet = publicWidget.Widget.extend({
    selector: '.o_wallet_operations',
    events: {
        'click #btnTopUpWallet': '_onClickBtnTopUpWallet',
        'click #btnWithdrawWallet': '_onClickBtnWithdrawWallet',
        'click #btnViewWalletTransactionHistory': '_onClickBtnViewWalletTransactionHistory',
    },

	init: function () {
		this._super.apply(this, arguments);
		this.orm = this.bindService('orm');
		this.dialog = this.bindService('dialog');
		this.notification = this.bindService('notification');
	},

    _onClickBtnTopUpWallet: function (ev) {
        const $btn = this.$('#btnTopUpWallet');
        const walletId = $btn.closest('div').attr('data-wallet-id')
        const walletName = $btn.closest('div').attr('data-wallet-name')
        var dialogData = {
			'wallet_id': parseInt(walletId),
			'title': _t('Top Up Wallet: %s', walletName),
			'precheck_method': 'check_before_top_up_wallet',
			'wallet_operation': 'top-up',
		};
        this._onOpenWalletPaymentDialog(dialogData);
    },

	_onClickBtnWithdrawWallet: function (ev) {
		const $btn = this.$('#btnWithdrawWallet');
        const walletId = $btn.closest('div').attr('data-wallet-id')
        const walletName = $btn.closest('div').attr('data-wallet-name')
        var dialogData = {
			'wallet_id': parseInt(walletId),
			'title': _t('Withdraw Wallet: %s', walletName),
			'precheck_method': 'check_before_withdraw_wallet',
			'wallet_operation': 'withdraw',
		};
        this._onOpenWalletPaymentDialog(dialogData);
    },

	_onClickBtnViewWalletTransactionHistory: function (ev) {
		const walletId = this.$('#btnViewWalletTransactionHistory').closest('div').attr('data-wallet-id');
		window.location.href = encodeURIComponent(`/wallets/transaction-history/${walletId}`);
	},

	_onOpenWalletPaymentDialog: function (dialogData) {
		var self = this;
		var location = window.location
		const dialogContent = renderToString('WalletPaymentDialog', dialogData);
		this.dialog.add(ConfirmationDialog, {
			title: dialogData.title,
			body: markup(dialogContent),
			confirmLabel: _t('Confirm'),
			confirm: async () => {
				const paymentAmount = document.getElementById('paymentAmount');
				const paymentAmountDisplay = document.getElementById('paymentAmountDisplay');
				if (!paymentAmountDisplay.checkValidity()) {
					this.notification.add(_t('Please enter amount!'), {
						title: _t("Warning"),
						type: 'warning',
					})
				} else if (parseFloat(paymentAmount.value) <= 0) {
					this.notification.add(_t('Amount must be positive!'), {
						title: _t("Warning"),
						type: 'warning',
					})

				} else {
					await self.orm.call(
						'wallet', dialogData.precheck_method,
						[dialogData.wallet_id, parseFloat(paymentAmount.value)],
						{
							context: {'portal_check_before_top_up_or_withdraw_wallet': true}
						}
					)

					location.href = await self.orm.call(
						'payment.transaction',
						'genarate_payment_link_top_up_or_withdraw_wallet',
						[dialogData.wallet_id, parseFloat(paymentAmount.value), dialogData.wallet_operation],
					);
				}
			},
			cancel: () => {} // show cancel button
		})
    },

});

publicWidget.registry.CreateWallet = publicWidget.Widget.extend({
    selector: '.o_create_wallet',
    events: {
        'click #btnCreateWallet': '_onClickBtnCreateWallet',
    },

	init: function () {
        this._super.apply(this, arguments);
        this.dialogData = null;
		this.dialog = this.bindService('dialog');
		this.notification = this.bindService('notification');
    },

	start: function () {
		this._loadData();
        return this._super.apply(this, arguments);
    },

	_loadData: function () {
		var self = this
		jsonrpc('/my/wallets/initialization-data').then(function (result) {
			self.dialogData = result;
		})
	},

    _onClickBtnCreateWallet: function (ev) {
		// debugger
		this._onOpenCreateWalletDialog(this.dialogData)
    },

	_onOpenCreateWalletDialog: function (dialogData) {
		const dialogContent = renderToString('CreateWalletDialogContent', {
			...dialogData,
			csrf_token: odoo.csrf_token
		})
		this.dialog.add(ConfirmationDialog, {
			title: _t('Add New Wallet'),
			body: markup(dialogContent),
			confirmLabel: _t('Confirm'),
			confirm: () => {
				const createWalletForm = document.getElementById('createWalletForm');
				// debugger
				const formValid = createWalletForm.reportValidity();
				if (!formValid) return;

				const formData = {};
				$(createWalletForm).serializeArray().forEach(field => {
					formData[field.name] = field.value;
				});
				jsonrpc('/my/wallets/create', formData).then(data => {
					if (data.success) {this.notification.add(_t('Create wallet successfully!'), {type: 'info'})
						location.reload();
						return;
					}
					this.notification.add(data.error, {
						'title': _t("Error"), type: 'danger'
					});
				});
				console.log('confirm')
			},
			cancel: () => {} // show cancel button
		});
    },

});
