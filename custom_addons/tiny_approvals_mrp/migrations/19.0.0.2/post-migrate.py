import logging

_logger = logging.getLogger(__name__)

# Tên phiếu tạo từ lệnh sản xuất đổi theo nút "Phê duyệt mua hàng"
RENAMES = [
    ('Phê duyệt xuất kho - ', 'Phê duyệt mua hàng - '),
    ('Stock Issue Approval - ', 'Purchase Approval - '),
]


def migrate(cr, version):
    """Đổi tên các phiếu phê duyệt mua hàng (mrp_stock) cũ "Phê duyệt xuất kho - ..." cho đồng bộ với phiếu mới.
    Chỉ đổi phần tiền tố, giữ nguyên phần tên lệnh sản xuất. Lỗi thì chỉ ghi log, không chặn nâng cấp."""
    try:
        with cr.savepoint():
            for old, new in RENAMES:
                cr.execute("""
                    UPDATE approval_request r
                       SET name = %s || substr(r.name, length(%s) + 1)
                      FROM approval_category c
                     WHERE r.category_id = c.id
                       AND c.approval_type = 'mrp_stock'
                       AND left(r.name, length(%s)) = %s
                """, (new, old, old, old))
                _logger.info('tiny_approvals_mrp: renamed %s approval requests from "%s" to "%s"', cr.rowcount, old, new)
    except Exception:
        _logger.exception('tiny_approvals_mrp: could not rename old stock approval requests')
