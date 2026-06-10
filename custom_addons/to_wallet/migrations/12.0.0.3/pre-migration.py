def migrate(cr, installed_version):
    cr.execute("""
        ALTER TABLE account_move_line
        ADD COLUMN IF NOT EXISTS wallet_id INTEGER
    """)
    cr.execute("""
        UPDATE account_move_line as aml
        SET wallet_id = payment.wallet_id
        FROM account_payment as payment
        WHERE aml.payment_id = payment.id
    """)
