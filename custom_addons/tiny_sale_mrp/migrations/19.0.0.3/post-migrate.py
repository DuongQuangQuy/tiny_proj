import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Tính lại tên đầy đủ của lệnh sản xuất cũ. Lúc tiny_mrp tạo cột thì code của module này chưa nạp,
    nên các lệnh cũ chỉ có số lệnh. Lỗi thì chỉ ghi log, không chặn việc nâng cấp."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    productions = env['mrp.production'].with_context(active_test=False).search([])
    try:
        with cr.savepoint():
            env.add_to_compute(productions._fields['full_name'], productions)
            productions.flush_recordset(['full_name'])
        _logger.info('tiny_sale_mrp: recomputed full_name for %s manufacturing orders', len(productions))
    except Exception:
        _logger.exception('tiny_sale_mrp: could not recompute full_name of manufacturing orders')
