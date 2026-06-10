from . import controllers
from . import models
from . import wizard
# from . import tests
from odoo.addons.payment import setup_provider, reset_payment_provider


def post_init_hook(env):
    setup_provider(env, 'wallet')


def uninstall_hook(env):
    reset_payment_provider(env, 'wallet')
