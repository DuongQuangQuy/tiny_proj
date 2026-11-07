# Tiny – Odoo 19 custom addons

Các module nằm trong `custom_addons/`. Hệ thống có 2 công ty: công ty thương mại (`res.company.is_service`)
bán cho khách, công ty sản xuất (`res.company.is_mrp`) sản xuất. Hai cờ này khai báo ở `tiny_contacts`.

## Chạy và test

Odoo source ở `D:\odoo19\odoo`, Python ở `D:\odoo19\odoo-env`, cấu hình ở `D:\odoo19\odoo.conf`
(PostgreSQL cổng 5433). `addons_path` trong `odoo.conf` đang trỏ dự án khác, nên phải truyền `--addons-path`.

Chạy test trên DB tạm, không dùng DB có sẵn. Từ `D:\odoo19` trong Git Bash:

```bash
export MSYS_NO_PATHCONV=1   # nếu thiếu, Git Bash biến tag /module thành đường dẫn Windows và 0 test chạy
ADDONS='D:\odoo19\odoo\odoo\addons,D:\odoo19\sun_proj\odoo-19.0+e.20260415\odoo\addons,D:\odoo19\tiny_proj\tiny_proj\custom_addons'
odoo-env/Scripts/python.exe odoo/odoo-bin -c odoo.conf --addons-path="$ADDONS" \
  -d tmp_tiny_test -i tiny_sale_mrp --without-demo=all --http-port=8199 --stop-after-init \
  --test-enable --test-tags=/tiny_sale_mrp --log-level=info --max-cron-threads=0
```

- `tiny_sale_mrp` phụ thuộc `mrp_workorder` (Enterprise), nên `--addons-path` trên dùng bộ Enterprise ở `sun_proj`.
- Kết quả nằm ở dòng log `odoo.tests.result` (mức info), nên đừng dùng `--log-level=warn`.
- `tiny_approvals_mrp` cần `approvals` (enterprise): thêm `D:\odoo19\dng_proj\ee_addons` vào `--addons-path`.
- Lệnh shell quá dài bị lỗi `ENAMETOOLONG` trên Windows, nên ghi file bằng Write thay vì heredoc dài.

## Luồng bán hàng liên công ty

```
SO (thương mại) -> PO (route MTO + Mua, tự xác nhận) -> SO (sản xuất) -> MO
```

- `tiny_sale_purchase`: `sale.order._action_confirm` xác nhận PO; `purchase.order._create_sale_company_mrp`
  tạo SO ở công ty sản xuất và chép số đo, ghi chú, mã vải, họa tiết từ dòng SO gốc.
- `tiny_sale_purchase_stock`: dòng SO công ty sản xuất lấy route có `stock.route.is_mrp = True`.
- `tiny_sale_mrp_trial_delivery`: `_get_origin_sale_order` truy ngược từ MO về SO gốc.

## tiny_sale_mrp: phiếu dự toán

Dành cho sản phẩm làm theo yêu cầu khách, chưa tồn tại lúc báo giá.

- Model: `sale.estimate` > `sale.estimate.line` (một sản phẩm yêu cầu) >
  `sale.estimate.bom.line` (NVL) và `sale.estimate.operation` (hoạt động).
- Chi phí hoạt động = phút/60 × (chi phí giờ + chi phí nhân công × `employee_ratio`), khớp `mrp_workorder`.
  `sale.estimate.instruction` (tab Hướng dẫn) thành `quality.point` trên hoạt động của BOM khi tạo đơn.
- Giá vốn đơn vị = NVL + hoạt động + chi phí khác. Giá bán = giá vốn × hệ số giá bán (`markup_factor`), sửa được.
- `action_create_sale_order` tạo sản phẩm dùng chung (`company_id = False`), nhà cung cấp là công ty sản xuất,
  BOM của công ty sản xuất và SO nháp. Sau đó luồng liên công ty giữ nguyên: MO tự tìm thấy BOM vì sản phẩm chỉ có một BOM.
- Đưa phiếu về nháp rồi tạo đơn lại sẽ dùng lại sản phẩm, lưu trữ BOM cũ và tạo BOM mới.
- Cấu hình bắt buộc trên công ty thương mại: `estimate_route_ids`.

## Lưu ý khi sửa code

- Dữ liệu của công ty sản xuất phải đọc bằng `sudo().with_company(...)`. `standard_price` phụ thuộc công ty
  nên đơn giá NVL dự toán lấy theo công ty sản xuất.
- Khu vực sản xuất của 2 công ty nối với nhau bằng `mrp.workcenter.code`, duy nhất trong từng công ty. Phiếu dự toán chọn
  khu vực công ty thương mại; chi phí theo giờ và BOM dùng khu vực cùng mã ở công ty sản xuất (`_get_mrp_workcenter`).
- Nhân viên bán hàng không có quyền `mrp.workcenter`. Ô chọn khu vực đi qua `mrp.workcenter.web_name_search` với context
  `sale_estimate_workcenter`, chỉ trả về id và tên.
- `code_fabric` và `note` khai báo riêng trên cả `product.template` và `product.product`, nên phải ghi cả hai nơi.
- `create()` không chạy onchange: tạo dòng SO bằng code phải tự truyền `image_128`, `code_fabric`, `product_pattern_image`.
- Tạo bản ghi có lịch làm việc cho công ty khác (như `mrp.workcenter`) phải dùng `with_company`, nếu không sẽ lỗi lệch công ty.
- Xác nhận SO ở công ty thương mại cần quyền Mua hàng, vì `tiny_sale_purchase` xác nhận PO bằng quyền người dùng hiện tại.

## Quy ước

- Nhãn, thông báo và comment viết bằng tiếng Việt.
- Commit theo dạng `[IMP] tên_module`.
- Module mới có `author` "Tiny", `website` https://tiny.com.vn/, `version` `19.0.0.1`, `license` LGPL-3.
