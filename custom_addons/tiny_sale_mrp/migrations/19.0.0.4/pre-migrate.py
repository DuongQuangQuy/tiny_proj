import logging

_logger = logging.getLogger(__name__)

BACKUP = 'code_fabric_text_bak'
TABLES = ['sale_estimate_line']


def _column_type(cr, table, column):
    cr.execute("""SELECT udt_name FROM information_schema.columns
                  WHERE table_schema = current_schema() AND table_name = %s AND column_name = %s""", (table, column))
    row = cr.fetchone()
    return row and row[0]


def _migrate_code_fabric(cr, table):
    """code_fabric: Char -> Many2one(product.product).
    Odoo 19 sẽ ép kiểu varchar::int4 và làm hỏng việc nâng cấp nếu có giá trị chữ như 'V01', nên trước khi nạp model:
    - đổi tên cột chữ cũ thành code_fabric_text_bak (giữ lại để tra cứu),
    - tạo sẵn cột int4 mới (ORM sẽ không tính lại trường compute trên dữ liệu cũ),
    - khớp chữ cũ với Mã nội bộ của sản phẩm (không phân biệt hoa thường), nếu không ra thì khớp đúng tên;
      chỉ nhận khi khớp duy nhất 1 sản phẩm. Lỗi khi khớp chỉ ghi log, không chặn nâng cấp."""
    col_type = _column_type(cr, table, 'code_fabric')
    if col_type not in ('varchar', 'text'):
        _logger.info('%s.code_fabric: column type %s, nothing to migrate', table, col_type)
        return
    if _column_type(cr, table, BACKUP):
        _logger.warning('%s.%s already exists, dropping it before backing up again', table, BACKUP)
        cr.execute('ALTER TABLE "%s" DROP COLUMN "%s"' % (table, BACKUP))
    cr.execute('ALTER TABLE "%s" RENAME COLUMN code_fabric TO "%s"' % (table, BACKUP))
    cr.execute('ALTER TABLE "%s" ADD COLUMN code_fabric int4' % table)
    try:
        cr.execute('SAVEPOINT code_fabric_map')
        cr.execute("""
            WITH src AS (
                SELECT DISTINCT btrim(t."{bak}") AS v FROM "{table}" t
                WHERE btrim(coalesce(t."{bak}", '')) <> ''
            ), by_code AS (
                SELECT s.v, min(pp.id) AS pid, count(*) AS c
                FROM src s JOIN product_product pp ON lower(btrim(pp.default_code)) = lower(s.v)
                WHERE pp.active GROUP BY s.v
            ), by_name AS (
                SELECT s.v, min(pp.id) AS pid, count(*) AS c
                FROM src s
                JOIN product_template pt ON lower(btrim(pt.name->>'vi_VN')) = lower(s.v)
                                         OR lower(btrim(pt.name->>'en_US')) = lower(s.v)
                JOIN product_product pp ON pp.product_tmpl_id = pt.id
                WHERE pp.active AND s.v NOT IN (SELECT v FROM by_code)
                GROUP BY s.v
            ), mapping AS (
                SELECT v, pid FROM by_code WHERE c = 1
                UNION ALL
                SELECT v, pid FROM by_name WHERE c = 1
            )
            UPDATE "{table}" t SET code_fabric = m.pid
            FROM mapping m WHERE btrim(t."{bak}") = m.v
        """.format(table=table, bak=BACKUP))
        mapped = cr.rowcount
        cr.execute("""SELECT btrim("{bak}"), count(*) FROM "{table}"
                      WHERE code_fabric IS NULL AND btrim(coalesce("{bak}", '')) <> ''
                      GROUP BY 1 ORDER BY 2 DESC""".format(table=table, bak=BACKUP))
        unmatched = cr.fetchall()
        cr.execute('RELEASE SAVEPOINT code_fabric_map')
        _logger.info('%s.code_fabric: mapped %s rows to products', table, mapped)
        if unmatched:
            _logger.warning('%s.code_fabric: %s distinct values (%s rows) not matched, kept in %s: %s',
                            table, len(unmatched), sum(c for _v, c in unmatched), BACKUP, unmatched[:100])
    except Exception:
        cr.execute('ROLLBACK TO SAVEPOINT code_fabric_map')
        _logger.exception('%s.code_fabric: could not map old text values, left empty (kept in %s)', table, BACKUP)


def migrate(cr, version):
    for table in TABLES:
        _migrate_code_fabric(cr, table)
