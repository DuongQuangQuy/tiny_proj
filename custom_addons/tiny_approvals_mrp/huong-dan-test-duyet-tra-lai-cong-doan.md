# Hướng dẫn test: Duyệt, trả lại và thời gian sửa công đoạn (tiny_approvals_mrp)

Nhánh: `tiny-mrp-duyet-cong-doan` (code nằm trong `tiny_approvals_mrp`, kế thừa `tiny_mrp`).

## 1. Lấy code và nâng cấp module
```bash
git fetch origin
git checkout <nhanh_moi>
./odoo-bin -c odoo.conf -d <ten_db_test> -u tiny_mrp,tiny_approvals_mrp --stop-after-init
```
Khởi động lại Odoo. Test trên DB bản sao, không dùng DB thật.

## 2. Cấu hình
1. **Người dùng** (Thiết lập > Người dùng). Nếu có `mrp_workorder` (Enterprise) thì mỗi user gắn một Nhân viên (HR).
   - Thợ cắt, thợ may, thợ vẽ, thợ finishing: user portal/nội bộ, không tích gì thêm.
   - Quản lý xưởng (người duyệt): user nội bộ, quyền Sản xuất > Người dùng.
   - Nhân viên kho (tích **Là nhân viên kho MRP**) để xác nhận kho như quy trình rập.
2. **Lý do** (Sản xuất > Cấu hình > Lý do): kiểm tra đã có các lý do mẫu, cột **Loại**:
   - Tạm dừng: "Chờ công đoạn trước chỉnh", "Chờ Vẽ"
   - Lỗi: "Sai họa tiết", "Lỗi đường may", "Sai kích thước"
3. **Khu vực sản xuất** (Sản xuất > Cấu hình > Khu vực sản xuất):

   | Khu vực | Nhân viên thực hiện | Điểm duyệt | Mặc định | Quản lý duyệt |
   |---|---|---|---|---|
   | Cắt | thợ cắt | Không có điểm duyệt | | |
   | May | thợ may | Quản lý chọn | Kiểm trước | Quản lý xưởng |
   | Vẽ | thợ vẽ | Bắt buộc duyệt | | Quản lý xưởng |
   | Finishing | thợ finishing | Bắt buộc duyệt | | Quản lý xưởng |

4. **Định mức (BOM)**, tab **Công đoạn**: Cắt (10) → May (20) → Vẽ (30) → Finishing (40). Kiểm tra cột Điểm duyệt / Quản lý duyệt tự lấy theo khu vực. Có thể giữ công đoạn rập như trước, các bước rập/kho vẫn chạy trước.

## 3. Kịch bản test

Chuẩn bị: tạo MO cho sản phẩm, Xác nhận, đi hết rập (nếu có) và **Xác nhận kho** để các công đoạn được bắt đầu.

### A. Duyệt bắt buộc (Vẽ)
| # | Ai | Làm gì | Kết quả mong đợi |
|---|----|--------|------------------|
| 1 | Thợ cắt, thợ may | Portal: Bắt đầu → Hoàn thành Cắt, May | May xong sinh yêu cầu duyệt lượt 1 (chế độ Kiểm trước) |
| 2 | Thợ vẽ | Portal `/my/workorders` → Bắt đầu Vẽ | Bị chặn: "Công đoạn May chưa được duyệt đạt" |
| 3 | Quản lý | Portal `/my/reviews` (hoặc Sản xuất > Duyệt công đoạn) | Thấy yêu cầu May, trạng thái Chờ quản lý duyệt |
| 4 | Quản lý | Bấm **Đạt** khi chưa nhận | Báo lỗi phải Nhận duyệt trước |
| 5 | Quản lý | **Nhận duyệt** → **Tạm dừng** → **Tiếp tục** → **Đạt** | Trạng thái đi đúng thứ tự; có người duyệt, thời gian duyệt |
| 6 | Thợ vẽ | Bắt đầu → Hoàn thành Vẽ | Chạy được; sinh yêu cầu duyệt Vẽ lượt 1 |

### B. Chưa đạt, chỉnh tại chỗ (thời gian sửa)
| # | Ai | Làm gì | Kết quả mong đợi |
|---|----|--------|------------------|
| 7 | Quản lý | Nhận duyệt Vẽ → **Chưa đạt**, lỗi "Sai họa tiết", công đoạn trả về = Vẽ | Vẽ quay về Sẵn sàng, badge "Đang sửa (lượt 1)"; MO về Đang thực hiện |
| 8 | Thợ vẽ | Mở Vẽ trên portal | Thấy khối Đang sửa: lý do, ghi chú, người trả |
| 9 | Thợ vẽ | Bắt đầu → Tạm dừng → Tiếp tục → Hoàn thành | Các phiên giờ mới có loại **Sửa**; sinh yêu cầu duyệt lượt 2 |
| 10 | Quản lý | Backend: MO > công đoạn Vẽ | Giờ làm mới giữ nguyên như trước bước 7, giờ sửa > 0, số lượt chỉnh = 1 |
| 11 | Quản lý | Duyệt Vẽ lượt 2 → Đạt | Finishing bắt đầu được |

### C. Trả về công đoạn trước
| # | Ai | Làm gì | Kết quả mong đợi |
|---|----|--------|------------------|
| 12 | Thợ finishing | Bắt đầu → Hoàn thành Finishing | Sinh yêu cầu duyệt Finishing |
| 13 | Quản lý | Nhận duyệt → Chưa đạt, lỗi "Lỗi đường may", trả về = **May**, người phụ trách = thợ may | May mở lại (Đang sửa); MO có message "Finishing bị trả về May" |
| 14 | Thợ finishing | Bắt đầu Finishing | Bị chặn: "Công đoạn May đang được chỉnh lại" |
| 15 | Thợ may | Sửa May và Hoàn thành | Giờ ghi loại Sửa; May sinh yêu cầu duyệt lượt 2 (Kiểm trước) |
| 16 | Quản lý | Duyệt May đạt | Finishing làm lại được (phiên giờ loại Sửa vì Finishing cũng đang có lượt chỉnh) |

### D. Kiểm sau và xuất xưởng
| # | Ai | Làm gì | Kết quả mong đợi |
|---|----|--------|------------------|
| 17 | Quản lý | MO mới: trên công đoạn May chọn **Kiểm sau** | Ghi người quyết định và thời điểm |
| 18 | Quản lý | Thử đổi chế độ trên Vẽ (bắt buộc) | Bị chặn |
| 19 | Thợ may, thợ vẽ | Hoàn thành May, rồi Bắt đầu Vẽ | Vẽ không bị chặn; yêu cầu duyệt May vẫn ở Chờ duyệt |
| 20 | Quản lý | Đi hết Vẽ, Finishing (duyệt đạt), bấm **Đánh dấu hoàn thành** MO | Bị chặn: còn yêu cầu duyệt May mở |
| 21 | Quản lý | Duyệt May đạt, đánh dấu hoàn thành lại | MO hoàn thành |

### E. Báo cáo
| # | Làm gì | Kết quả mong đợi |
|---|--------|------------------|
| 22 | Sản xuất > Báo cáo > Thời gian làm mới / sửa | Pivot theo khu vực × Làm mới/Sửa, số khớp với các bước trên |
| 23 | Form MO, tab Duyệt & chỉnh | Thấy đủ các lượt duyệt, lượt trả lại, tổng giờ làm mới / giờ sửa / giờ duyệt |
| 24 | Sản xuất > Vận hành > Lịch sử trả lại | Mỗi lượt có từ công đoạn, về công đoạn, lý do, ngày trả, ngày chỉnh xong, giờ sửa |

## 4. Hồi quy
- BOM không có khu vực nào có điểm duyệt: MO chạy y như trước, không sinh yêu cầu duyệt, không bị chặn.
- Quy trình rập (Xác nhận NVL rập → Xác nhận kho) vẫn chạy như hướng dẫn test công đoạn rập.
- Tạm dừng trên portal chỉ hiện lý do loại Tạm dừng.
- Lệnh rập phụ kiểu cũ không bị áp chặn duyệt.
