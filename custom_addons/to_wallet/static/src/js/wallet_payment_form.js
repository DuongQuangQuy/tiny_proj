/** @odoo-module **/

import PaymentForm from "@payment/js/payment_form"
import {_t} from "@web/core/l10n/translation";
import {jsonrpc, RPCError} from "@web/core/network/rpc_service";


PaymentForm.include({

	/** 
	 * Add `wallet_id` to the transaction route params if it is provided.
	 * 
	 * @private
	 * @return {object} The transaction route params.
	 */
	_prepareTransactionRouteParams() {
		const transactionRouteParams = this._super(...arguments);
		if (this.paymentContext['walletId']) {
			return {
				...transactionRouteParams,
				'wallet_id': parseInt(this.paymentContext['walletId']),
			}
		}
		return transactionRouteParams
	},

    /**
     * Overridden to prepare the inline form of Wallet for direct payment flow.
	 * 
     * For a provider to manage an inline form, it must override this method and render the content
     * of the form.
     *
     * @private
     * @param {number} providerId - The id of the selected payment option's provider.
     * @param {string} providerCode - The code of the selected payment option's provider.
     * @param {number} paymentOptionId - The id of the selected payment option.
     * @param {string} paymentMethodCode - The code of the selected payment method, if any.
     * @param {string} flow - The online payment flow of the selected payment option.
     * @return {void}
     */
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode !== 'wallet') {
            return this._super(...arguments);
        }
        this._setPaymentFlow('direct');
        return Promise.resolve()
    },

    /**
     * Overridden to simulate a feedback from a payment provider and redirect the customer to the status page.
	 * 
	 * Process the provider-specific implementation of the direct payment flow.
	 * 
	 * @private
     * @param {string} providerCode - The code of the selected payment option's provider.
     * @param {number} paymentOptionId - The id of the selected payment option.
     * @param {string} paymentMethodCode - The code of the selected payment method, if any.
     * @param {object} processingValues - The processing values of the transaction.
     * @return {void}
     */
    _processDirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'wallet') {
            return this._super(...arguments);
        }
        const walletId = document.getElementById('wallet').value;
        jsonrpc('/my/wallets/payment/status', {
            'reference': processingValues.reference,
            'wallet_id': parseInt(walletId)
        }).then(() => {
            window.location = '/payment/status';
        }).catch(error => {
            if (error instanceof RPCError) {
                this._displayErrorDialog(_t("Payment processing failed"), error.data.message);
                this._enableButton?.(); // This method doesn't exists in Express Checkout form.
            } else {
                return Promise.reject(error);
            }
        });
    },
});
