# TECHSPEC — tiny_sale_advance_wallet

## Mục đích module
Mở rộng chức năng đặt cọc (`sale_advance_payment`) để hỗ trợ thêm phương thức thanh toán qua **ví điện tử** (`to_wallet`), bên cạnh 2 phương thức sẵn có là tiền mặt và ngân hàng.

---

## Phụ thuộc (Dependencies)
- `sale_advance_payment` — module gốc quản lý đặt cọc trên sale order
- `to_wallet` — module quản lý ví điện tử của partner

---

## Cấu trúc file

```
tiny_sale_advance_wallet/
├── models/
│   ├── sale_advance_line.py   → Model sale.advance.line
│   └── sale_order.py          → Inherit sale.order
├── wizard/
│   ├── sale_advance_payment_wzd.py       → Inherit account.voucher.wizard
│   └── sale_advance_payment_wzd_view.xml → Override form wizard
├── views/
│   └── sale_advance_line_views.xml → Tree + tab trên Sale Order
├── security/
│   └── ir.model.access.csv
└── __manifest__.py
```

---

## Model: `sale.advance.line`

Model mới lưu lịch sử từng khoản đặt cọc / hoàn cọc, thay thế việc compute trực tiếp từ `account.payment` (để tránh lệch số tiền khi dùng ví).

### Fields chính

| Field | Type | Mô tả |
|---|---|---|
| `date` | Date | Ngày giao dịch |
| `sale_id` | Many2one `sale.order` | Sale order liên kết |
| `partner_id` | related `sale_id.partner_invoice_id` | Khách hàng |
| `company_id` | Many2one `res.company` | Công ty |
| `currency_id` | Many2one `res.currency` | Tiền tệ |
| `advance_type` | Selection: `cash/bank/wallet` | Phương thức thanh toán |
| `transaction_type` | Selection: `deposit/refund` | Loại giao dịch |
| `amount` | Monetary | Số tiền |
| `state` | computed: `posted/cancel` | Trạng thái (từ payment hoặc wallet_history) |
| `payment_id` | Many2one `account.payment` | Link payment (cash/bank) |
| `wallet_history_id` | Many2one `wallet.history` | Link wallet history (wallet) |
| `move_id` | Many2one `account.move` | Link journal entry (dự phòng) |

### Tại sao cần model này?
Module `sale_advance_payment` gốc compute `total_advance` từ `account_payment_ids.move_id.line_ids.amount_residual`. Nếu dùng payment nạp ví để track → hiển thị sai số tiền (payment nạp ví = 5tr nhưng advance chỉ 2tr). Model `sale.advance.line` lưu đúng số tiền thực tế của từng khoản đặt cọc.

---

## Model: `sale.order` (inherit)

### Field mới
- `advance_line_ids` — One2many đến `sale.advance.line`

### Override `_compute_advance_payment`
Gọi `super()` trước để tính phần bank/cash, sau đó **cộng thêm** phần wallet:

```python
wallet_net = wallet_deposit - wallet_refund
order.total_advance += wallet_net
order.amount_residual -= wallet_net
```

Cập nhật `advance_payment_status` sau khi cộng wallet net.

**Lưu ý:** Chỉ tính các dòng có `advance_type='wallet'` và `state != 'cancel'`.

---

## Wizard: `account.voucher.wizard` (inherit)

### Fields mới

| Field | Mô tả |
|---|---|
| `is_wallet` | Boolean — bật/tắt chế độ thanh toán qua ví |
| `journal_id` | Override `required=False` (validation thủ công trong `make_advance_payment`) |
| `wallet_id` | Many2one `wallet` — ví của partner |
| `wallet_type_id` | Many2one `wallet.type` — loại ví (dùng để tìm/tạo ví) |
| `partner_id` | computed từ `order_id` — dùng cho domain `wallet_id` |
| `company_id` | computed từ `order_id` — dùng cho domain `wallet_id` |

### Logic `make_advance_payment`

```
if is_wallet:
    if inbound → _create_wallet_advance()
    if outbound → _create_wallet_refund()
else:
    validate journal_id
    if outbound → validate còn khoản đặt cọc không
    → _create_cash_bank_advance()
```

### `_create_wallet_advance` (đặt cọc qua ví)
1. Validate số dư ví (`_check_wallet_balance`)
2. Gọi `wallet._create_wallet_history(amount=-amount, history_type='payment', force_done=True)`
3. Tạo `sale.advance.line` với `transaction_type='deposit'`, `advance_type='wallet'`

### `_create_cash_bank_advance` (đặt cọc tiền mặt/ngân hàng)
1. Gọi `_prepare_payment_vals` → tạo `account.payment` → post
2. Link payment vào `sale.account_payment_ids`
3. Tạo `sale.advance.line` với `advance_type` lấy từ journal type (`cash/bank`), `transaction_type` từ `payment_type`

### `_create_wallet_refund` (hoàn cọc qua ví)

**Logic split:**
```
remaining_wallet_advance = wallet_deposited - wallet_refunded (đã hoàn trước đó)

if remaining_wallet_advance > 0:
    refund_part = min(amount, remaining_wallet_advance)
    → wallet.history type='refund'    → sale.advance.line deposit/refund
    
    topup_part = amount - refund_part
    if topup_part > 0:
        → wallet.history type='top-up'  → sale.advance.line refund
else:
    → wallet.history type='top-up'  → sale.advance.line refund
```

**Giải thích:** Phần hoàn trả nằm trong số tiền đã đặt cọc qua ví → dùng `refund`. Phần vượt quá (hoặc không có wallet advance gốc) → dùng `top-up` (nạp thêm vào ví).

**Validation:** Raise `UserError` nếu tổng deposit (mọi loại) - tổng refund ≤ 0.

---

## View

### Wizard form (`sale_advance_payment_wzd_view.xml`)
- `is_wallet` checkbox sau `payment_type`
- `wallet_type_id`, `wallet_id` hiện khi `is_wallet=True`
- `journal_id` hiển thị **2 lần** với domain khác nhau:
  - `is_wallet=False` → domain `type in (bank, cash)`
  - `is_wallet=True` → domain `type = general`

### Sale Order form (`sale_advance_line_views.xml`)
- Tab mới **"Các khoản đặt cọc"** trong notebook, hiển thị `advance_line_ids`
- Tree: date, advance_type, transaction_type, payment_id, wallet_history_id, amount (sum), state
- `readonly=True` — không cho sửa trực tiếp

---

## Luồng kế toán

### Đặt cọc bank/cash
Giữ nguyên luồng gốc của `sale_advance_payment`:
- Tạo `account.payment` → post → credit receivable
- Khi invoice confirm → auto reconcile credit receivable với debit receivable của invoice

### Đặt cọc ví
- **Không tạo `account.payment`**
- Trực tiếp tạo `wallet.history` type `payment` (amount âm → trừ ví)
- Tracking qua `sale.advance.line` (không qua `account_payment_ids`)
- **Chưa có journal entry riêng** — phần reconcile invoice với wallet credit lines vẫn cần xử lý thêm nếu cần tự động

### Hoàn cọc ví
- Tạo `wallet.history` type `refund` hoặc `top-up` (amount dương → cộng ví)
- Tạo `sale.advance.line` tương ứng
- Không tạo `account.payment`

---

## Điểm cần chú ý khi điều chỉnh

1. **`wallet_type_id._check_wallet_history_type`** — mỗi `wallet.type` có cấu hình cho phép loại history nào. Nếu wallet type không cho phép `payment` hoặc `refund` → sẽ raise lỗi. Cần đảm bảo wallet type cấu hình đúng.

2. **`_compute_advance_payment` double-dependency** — method này depend vào cả `account_payment_ids` (từ module gốc) và `advance_line_ids` (module này). Tránh tạo circular dependencies.

3. **`advance_payment_status`** — khi `wallet_net = 0` (không có khoản ví), trạng thái hoàn toàn do logic gốc quyết định. Module này chỉ can thiệp khi `wallet_net > 0`.

4. **`journal_id` override `required=False`** — quan trọng để wizard không lỗi khi `is_wallet=True`. Validation journal được thực hiện thủ công trong `make_advance_payment`.

5. **Currency** — `sale.advance.line.currency_id` dùng `sale.currency_id` cho wallet advances, `journal_currency_id` cho cash/bank advances. Cần nhất quán khi tính tổng trong compute.
