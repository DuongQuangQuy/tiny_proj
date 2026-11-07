# Hướng dẫn cấu hình và test module Tiny: Sale MRP

Module `tiny_sale_mrp` thêm **Phiếu dự toán**: tính giá cho sản phẩm làm theo yêu cầu khách khi sản phẩm chưa tồn tại.
Khi khách đồng ý, phiếu tự tạo sản phẩm, BOM ở công ty sản xuất và đơn bán hàng ở công ty thương mại.

```
Phiếu dự toán -> SO công ty thương mại -> PO (tự xác nhận) -> SO công ty sản xuất -> MO
```

Tên menu và trường dưới đây ghi theo giao diện tiếng Việt, kèm tên tiếng Anh trong ngoặc khi cần. Bản dịch có thể khác
đôi chút nếu DB chưa cập nhật tiếng Việt.

---

## 1. Cài đặt module

Module phụ thuộc `sale_mrp`, `mrp_workorder`, `tiny_contacts`, `tiny_product`, `tiny_sale_purchase_stock`. Odoo tự cài các
module này nếu chúng nằm trong `addons_path`. `mrp_workorder` là module **Enterprise**, nên `addons_path` phải có bộ
Enterprise. Các lệnh dưới đây dùng bản ở `sun_proj` trên máy này, hãy đổi nếu dự án dùng đường dẫn khác.

Từ `D:\odoo19` trong Git Bash, thay `<ten_db>` bằng DB cần cài:

```bash
export MSYS_NO_PATHCONV=1
ADDONS='D:\odoo19\odoo\odoo\addons,D:\odoo19\sun_proj\odoo-19.0+e.20260415\odoo\addons,D:\odoo19\tiny_proj\tiny_proj\custom_addons'
odoo-env/Scripts/python.exe odoo/odoo-bin -c odoo.conf --addons-path="$ADDONS" \
  -d <ten_db> -i tiny_sale_mrp --stop-after-init
```

Khi nâng cấp module đã cài, đổi `-i` thành `-u`.

---

## 2. Cấu hình (làm một lần)

Dùng tài khoản quản trị có quyền trên cả 2 công ty. Các bước dưới đây phải làm đủ: thiếu bước nào thì luồng dừng ở bước đó
(xem [mục 6](#6-xử-lý-sự-cố)).

### 2.1. Bật tính năng

| Ở đâu | Bật | Để làm gì |
|---|---|---|
| Tồn kho > Cấu hình > Thiết lập | **Tuyến cung ứng nhiều bước** (Multi-Step Routes) | Hiện menu Tuyến cung ứng |
| Sản xuất > Cấu hình > Thiết lập | **Công đoạn** (Work Orders) | Hiện menu Khu vực sản xuất |

### 2.2. Khai báo 2 công ty

Vào **Thiết lập > Người dùng & Công ty > Công ty**.

| Công ty | Trường | Giá trị |
|---|---|---|
| Công ty thương mại | **Công ty thương mại** | Bật |
| Công ty sản xuất | **Công ty sản xuất** | Bật |

Chỉ bật **Công ty sản xuất** ở đúng 1 công ty, vì hệ thống lấy công ty đầu tiên tìm được.

Nên dùng cùng tiền tệ cho 2 công ty. Nếu khác tiền tệ, phải có tỷ giá để quy đổi giá vốn.

### 2.3. Kiểm tra mỗi công ty có kho

Công ty tạo mới **không tự có kho**. Chuyển sang từng công ty, vào **Tồn kho > Cấu hình > Quản lý kho > Kho hàng**,
tạo kho nếu chưa có. Ví dụ mã kho `TM` cho công ty thương mại, `SX` cho công ty sản xuất.

### 2.4. Mở tuyến MTO

Tuyến MTO mặc định bị lưu trữ.

1. Vào **Tồn kho > Cấu hình > Quản lý kho > Tuyến cung ứng**.
2. Lọc **Đã lưu trữ**, mở **Bổ sung theo đơn đặt hàng (MTO)** (Replenish on Order).
3. Chọn **Hành động > Hủy lưu trữ**.

### 2.5. Cấu hình tuyến Sản xuất

Chuyển sang **công ty sản xuất**, mở tuyến **Sản xuất** (Manufacture) rồi:

1. Bật **Chi tiết đơn bán hàng** (Sales Order Lines) ở nhóm *Có thể áp dụng cho*.
2. Bật **Là sản xuất**. Chỉ bật ở đúng 1 tuyến.
3. Ở mục **Quy tắc**, thêm dòng mới:

| Trường | Giá trị |
|---|---|
| Tên | Giao từ kho SX theo MTO |
| Hành động | Kéo từ (Pull From) |
| Loại hoạt động | Phiếu xuất kho của kho công ty sản xuất, ví dụ `SX: Delivery Orders` |
| Vị trí nguồn | Kho chính của công ty sản xuất, ví dụ `SX/Stock` |
| Vị trí đích | `Partners/Customers` |
| Phương thức cung ứng | **Kích hoạt một quy tắc khác** (Trigger Another Rule) |
| Công ty | Công ty sản xuất |

Quy tắc này là điều kiện để sinh MO. Thiếu nó, SO công ty sản xuất chỉ xuất từ tồn kho và không tạo lệnh sản xuất.

### 2.6. Cấu hình phiếu dự toán trên công ty thương mại

Mở lại form **công ty thương mại**. Ba trường này chỉ hiện khi đã bật **Công ty thương mại**.

| Trường | Giá trị | Bắt buộc |
|---|---|---|
| Tuyến cho sản phẩm dự toán | **MTO** và **Mua** (Buy) | Có |
| Danh mục sản phẩm dự toán | Danh mục mặc định trên dòng dự toán | Không |
| Hệ số giá bán mặc định | Ví dụ `2` là bán gấp đôi giá vốn | Không |

### 2.7. Tạo dữ liệu mẫu

Dữ liệu dưới đây dùng cho các kịch bản ở mục 4.

**Nguyên vật liệu `Vải A`** (Tồn kho > Sản phẩm)

- Theo dõi tồn kho: bật.
- **Công ty: để trống.** Phiếu dự toán chỉ chọn được NVL dùng chung.
- Giá vốn: chuyển sang **công ty sản xuất** rồi nhập `100.000`. Phiếu dự toán lấy giá vốn theo công ty sản xuất,
  nên giá vốn nhập ở công ty thương mại không có tác dụng.

**Khu vực sản xuất `May`** (Sản xuất > Cấu hình > Khu vực sản xuất)

Tạo ở **cả 2 công ty**, hai bên dùng chung **Mã**. Mã là thứ nối khu vực của 2 công ty, tên có thể khác nhau.

| Công ty | Tên | Mã | Chi phí theo giờ |
|---|---|---|---|
| Công ty thương mại | May | `MAY` | Không dùng cho dự toán |
| Công ty sản xuất | May | `MAY` | `60.000` |

Mã không được trùng trong cùng một công ty.

**Khách hàng `Khách lẻ`**: tạo ở công ty thương mại hoặc để dùng chung.

**Nhân viên kinh doanh** (Thiết lập > Người dùng)

- Công ty: chỉ công ty thương mại.
- Bán hàng: **Người dùng** (User: Own Documents Only).
- Mua hàng: **Người dùng**. Thiếu quyền này, nhân viên không xác nhận được SO.

---

## 3. Sử dụng

Đăng nhập tài khoản nhân viên kinh doanh, vào **Bán hàng > Đơn hàng > Phiếu dự toán**, nhấn **Mới**.

1. Chọn **Khách hàng**.
2. Ở tab **Sản phẩm yêu cầu**, thêm dòng. Mỗi dòng là một sản phẩm sẽ tạo mới.
3. Nhập yêu cầu của khách: tên, số lượng, số đo, mã vải, ghi chú, họa tiết, hình ảnh.
4. Tab **Nguyên vật liệu**: chọn NVL và định mức cho **1 sản phẩm**. Đơn giá tự lấy, sửa được.
5. Tab **Hoạt động**: nhấn **Thêm hoạt động**, nhập tên hoạt động, chọn khu vực của công ty thương mại và thời lượng cho
   1 sản phẩm. Nếu để trống tên, hệ thống lấy theo tên khu vực. Chi phí theo giờ tự lấy từ
   khu vực cùng mã ở công ty sản xuất, sửa được. BOM tạo ra dùng khu vực của công ty sản xuất.
6. Nhập **Chi phí khác** (tính trên 1 sản phẩm) và **Hệ số giá bán**, ví dụ `2` là nhân 2, `3` là nhân 3, `1,5` là nhân 1,5.
7. Lưu phiếu, nhấn **Tạo đơn hàng**.

Cách tính giá:

```
Chi phí NVL       = Tổng (định mức x đơn giá NVL)
Chi phí hoạt động = Tổng (số phút / 60 x (chi phí theo giờ + chi phí nhân công theo giờ x khả năng nhân viên))
Giá vốn đơn vị    = Chi phí NVL + Chi phí hoạt động + Chi phí khác
Giá bán đơn vị    = Giá vốn đơn vị x hệ số giá bán
```

Công thức chi phí hoạt động giống BOM Enterprise. Chi phí nhân công lấy từ khu vực cùng mã ở công ty sản xuất.

Tab **Hướng dẫn** trong popup hoạt động dùng để ghi các bước cho thợ. Khi tạo đơn, mỗi dòng trở thành một hướng dẫn trên
hoạt động của BOM ở công ty sản xuất.

Popup hoạt động có thêm 2 trường chuyển sang BOM, không làm đổi giá dự toán:

- **Tính toán thời lượng**: Cố định, hoặc Tính toán theo số lệnh gần nhất. Dự toán luôn dùng Thời lượng mặc định.
- **Chi phí dựa trên**: Thời gian thực tế hoặc Thời gian lý thuyết.

Lưu ý khi nhập:

- **Thời lượng/1 SP** tính bằng phút và hiển thị dạng `phút:giây`. Nhập `30:00` là 30 phút, còn `00:30` chỉ là 30 giây.
- **Giá bán đơn vị** sửa tay được, nhưng sẽ bị tính lại khi giá vốn hoặc hệ số giá bán đổi. Hãy sửa giá bán sau cùng.

---

## 4. Kịch bản test

Mỗi kịch bản bắt đầu bằng một phiếu mới, trừ khi ghi khác. Phiếu mẫu dùng cho các kịch bản:

| Trường | Giá trị |
|---|---|
| Khách hàng | Khách lẻ |
| Tên sản phẩm | Sofa may đo |
| Số lượng | 2 |
| Số đo / Mã vải | 2m x 1m / V01 |
| Chi phí khác | 50.000 |
| Hệ số giá bán | 1,2 |
| Nguyên vật liệu | Vải A, định mức 3 |
| Hoạt động | May, thời lượng `30:00` |

### TC1. Tính giá

Nhập phiếu mẫu, lưu. Chưa nhấn Tạo đơn hàng.

| Trường | Kết quả đúng |
|---|---|
| Đơn giá NVL | 100.000 |
| Chi phí NVL | 300.000 |
| Chi phí hoạt động | 30.000 |
| Giá vốn đơn vị | 380.000 |
| Giá bán đơn vị | 456.000 |
| Tổng giá vốn | 760.000 |
| Tổng giá bán | 912.000 |
| Lợi nhuận dự kiến | 152.000 |

### TC2. Tạo đơn hàng

Nhấn **Tạo đơn hàng** trên phiếu TC1.

- Phiếu chuyển sang **Đã tạo đơn hàng**, có nút **Đơn hàng**.
- SO ở trạng thái báo giá, `Nguồn` là số phiếu, đơn giá 456.000, số lượng 2, có số đo và mã vải.
- Trên form dòng dự toán có mục **Đã tạo** với sản phẩm và BOM.
- Sản phẩm có mã `<số phiếu>-01`, trường Công ty để trống, tuyến là MTO và Mua.
- Tab mua hàng của sản phẩm có nhà cung cấp là công ty sản xuất, giá 380.000.
- BOM (xem ở công ty sản xuất) gồm Vải A định mức 3, hoạt động May 30 phút.

### TC3. Luồng liên công ty đến MO

Nhấn **Xác nhận** trên SO của TC2. Sau đó chuyển sang tài khoản quản trị để xem chứng từ của cả 2 công ty.

| Chứng từ | Công ty | Kết quả đúng |
|---|---|---|
| SO gốc | Thương mại | Đơn bán hàng |
| PO | Thương mại | Nhà cung cấp là công ty sản xuất, đã xác nhận, đơn giá 380.000 |
| Phiếu nhập `TM/IN` | Thương mại | Chờ hàng từ PO |
| SO mới | Sản xuất | Đã xác nhận, `Nguồn` là số PO, khách là công ty thương mại, đơn giá 380.000, tuyến Sản xuất, có số đo |
| MO | Sản xuất | Đã xác nhận, số lượng 2, dùng đúng BOM của phiếu |
| NVL trên MO | Sản xuất | Vải A, số lượng 6 |
| Công đoạn trên MO | Sản xuất | May, thời lượng dự kiến 60 phút |

### TC4. Mở lại phiếu để sửa

Dùng phiếu mới đã qua TC2, **chưa xác nhận SO**.

1. Trên phiếu, nút **Đưa về nháp** chưa hiện vì SO còn hiệu lực.
2. Hủy SO. Nút **Đưa về nháp** xuất hiện, nhấn nút này.
3. Sửa định mức Vải A thành 5, lưu, nhấn **Tạo đơn hàng**.

Kết quả đúng:

- Vẫn là sản phẩm cũ, không tạo sản phẩm mới.
- BOM cũ bị lưu trữ, BOM mới có định mức 5.
- Sản phẩm chỉ có 1 dòng nhà cung cấp, giá 580.000.

### TC5. Nhân bản phiếu

Nhân bản một phiếu đã tạo đơn hàng.

Phiếu mới ở trạng thái **Nháp**, giữ NVL và hoạt động, chưa có sản phẩm và BOM.

### TC6. Hủy và xóa phiếu

| Thao tác | Kết quả đúng |
|---|---|
| Phiếu nháp: nhấn **Hủy** | Phiếu chuyển sang Đã hủy |
| Phiếu có SO còn hiệu lực | Nút **Hủy** không hiện |
| Xóa phiếu đã có SO | Báo `Không thể xóa phiếu dự toán đã có đơn bán hàng.` |

### TC7. Các trường hợp bị chặn

Nhấn **Tạo đơn hàng** trong từng trường hợp. Phiếu giữ nguyên, không sinh sản phẩm hay đơn hàng.

| Điều kiện | Thông báo |
|---|---|
| Phiếu không có dòng sản phẩm | `Phiếu dự toán chưa có sản phẩm.` |
| Dòng không có NVL | `Các sản phẩm sau chưa có định mức nguyên vật liệu: ...` |
| Công ty chưa cấu hình tuyến | `Công ty ... chưa cấu hình Tuyến cho sản phẩm dự toán.` |
| Khu vực trên phiếu không còn khu vực cùng mã ở công ty sản xuất | `Các khu vực sau chưa có khu vực cùng mã ở công ty sản xuất: ...` |
| Công ty của phiếu chưa bật Công ty thương mại | `Công ty ... chưa được đánh dấu là công ty thương mại.` |
| Không có công ty nào bật Công ty sản xuất | `Chưa cấu hình công ty sản xuất (Công ty sản xuất trên form công ty).` |

### TC8. Phân quyền nhân viên kinh doanh

Tài khoản nhân viên chỉ có công ty thương mại.

| Thao tác | Kết quả đúng |
|---|---|
| Chọn khu vực sản xuất trên tab Hoạt động | Chỉ thấy khu vực của công ty thương mại đã có khu vực cùng mã ở công ty sản xuất |
| Chọn NVL | Không thấy NVL riêng của từng công ty, đơn giá vẫn lấy theo công ty sản xuất |
| Tạo đơn hàng | Thành công dù không có quyền tạo sản phẩm và BOM |
| Xác nhận SO khi có nhóm Mua hàng | Thành công |
| Xác nhận SO khi không có nhóm Mua hàng | Báo lỗi không có quyền sửa Đơn mua hàng |

---

## 5. Chạy test tự động

Module có 15 test ở `tests/test_sale_estimate.py`. Bộ test tự dựng dữ liệu, nên chạy trên DB tạm, không dùng DB đang làm việc.

Từ `D:\odoo19` trong Git Bash:

```bash
export MSYS_NO_PATHCONV=1   # nếu thiếu, Git Bash biến tag /module thành đường dẫn Windows và 0 test chạy
ADDONS='D:\odoo19\odoo\odoo\addons,D:\odoo19\sun_proj\odoo-19.0+e.20260415\odoo\addons,D:\odoo19\tiny_proj\tiny_proj\custom_addons'
odoo-env/Scripts/python.exe odoo/odoo-bin -c odoo.conf --addons-path="$ADDONS" \
  -d tmp_tiny_test -i tiny_sale_mrp --without-demo=all --http-port=8199 --stop-after-init \
  --test-enable --test-tags=/tiny_sale_mrp --log-level=info --max-cron-threads=0
```

Kết quả đúng, ở cuối log:

```
odoo.tests.result: 0 failed, 0 error(s) of 15 tests when loading database 'tmp_tiny_test'
```

Xóa DB tạm sau khi chạy:

```bash
odoo-env/Scripts/python.exe odoo/odoo-bin db -c odoo.conf drop tmp_tiny_test
```

---

## 6. Xử lý sự cố

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Không thấy menu Tuyến cung ứng | Chưa bật Multi-Step Routes | Mục 2.1 |
| Không thấy menu Khu vực sản xuất | Chưa bật Work Orders | Mục 2.1 |
| Không chọn được kho, loại hoạt động hoặc vị trí của công ty sản xuất | Công ty chưa có kho | Mục 2.3 |
| Không thấy NVL trong ô chọn | NVL có gán Công ty, hoặc không phải hàng hóa | Để trống Công ty trên sản phẩm |
| Đơn giá NVL bằng 0 | Giá vốn chưa nhập ở công ty sản xuất | Chuyển sang công ty sản xuất rồi nhập giá vốn |
| Không chọn được khu vực sản xuất | Khu vực chưa có Mã, hoặc chưa có khu vực cùng mã ở công ty sản xuất | Mục 2.7 |
| Chi phí theo giờ bằng 0 | Khu vực cùng mã ở công ty sản xuất có chi phí 0 hoặc đã đổi mã | Sửa ở khu vực của công ty sản xuất |
| Báo mã khu vực đã được dùng | Hai khu vực trong cùng công ty trùng mã | Đổi mã một khu vực |
| Chi phí hoạt động rất nhỏ | Nhập `00:30` thay vì `30:00` | Xem lưu ý ở mục 3 |
| Xác nhận SO bị lỗi không có quyền sửa Đơn mua hàng | Người xác nhận thiếu nhóm Mua hàng | Mục 2.7 |
| Xác nhận SO nhưng không có PO | Tuyến MTO hoặc Mua thiếu trên công ty, hoặc tuyến MTO còn lưu trữ | Mục 2.4 và 2.6, rồi tạo lại đơn từ phiếu mới |
| Có SO công ty sản xuất nhưng không có MO | Tuyến Sản xuất thiếu **Là sản xuất** hoặc thiếu quy tắc | Mục 2.5 |

Tuyến gán cho sản phẩm lúc nhấn **Tạo đơn hàng**. Vì vậy sau khi sửa cấu hình ở mục 2.6, phiếu đã tạo đơn trước đó không tự
cập nhật: hãy test bằng phiếu mới.

---

## 7. Giới hạn hiện tại

- Luồng của module dừng ở MO. Sản xuất, giao hàng và nhập kho giữa 2 công ty sau MO thuộc quy trình có sẵn, không nằm trong
  các kịch bản trên.
- TC4 chỉ áp dụng cho SO chưa xác nhận. Chưa có kịch bản cho trường hợp hủy SO đã sinh PO, SO công ty sản xuất và MO.
