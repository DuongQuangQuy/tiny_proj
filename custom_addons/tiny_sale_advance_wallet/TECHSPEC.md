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
│   ├── __init__.py
│   ├── sale_advance_line.py   → Model sale.advance.line
│   ├── sale_order.py          → Inherit sale.order
│   └── account_move.py        → Inherit account.move (auto-reconcile invoice)
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
| `move_id` | Many2one `account.move` | Link journal entry của wallet advance/refund |

### Tại sao cần model này?
Module `sale_advance_payment` gốc compute `total_advance` từ `account_payment_ids.move_id.line_ids.amount_residual`. Nếu dùng payment nạp ví để track → hiển thị sai số tiền (payment nạp ví = 5tr nhưng advance chỉ 2tr). Model `sale.advance.line` lưu đúng số tiền thực tế của từng khoản đặt cọc.

---

## Model: `sale.order` (inherit)

### Field mới
- `advance_line_ids` — One2many đến `sale.advance.line`

### Override `_compute_advance_payment`
Gọi `super()` trước để tính phần bank/cash, sau đó **cộng thêm** phần wallet từ CR line của journal entry:

```python
# Lấy CR lines (no wallet_id, credit > 0) từ wallet advance moves
cr_lines = wallet_moves.mapped('line_ids').filtered(
    lambda l: l.account_id.account_type == 'asset_receivable'
    and not l.wallet_id and l.credit > 0 and l.parent_state == 'posted'
)
wallet_amount = sum(abs(line.amount_residual) for line in cr_lines)  # có convert currency
order.total_advance += wallet_amount
order.amount_residual -= wallet_amount
```

**Lý do dùng `amount_residual` thay vì static amount:** Khi CR line được reconcile với invoice, `amount_residual` về 0 → tránh double-count (vì invoice đã tính khoản đó qua `invoice_paid_amount`).

**Lưu ý:** Chỉ tính các dòng có `advance_type='wallet'`, `state != 'cancel'`, và `move_id` tồn tại.

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

### `_prepare_wallet_advance_move_vals` (helper)
Tạo vals cho journal entry đặt cọc ví:
```
DR Receivable (wallet_id=W)   = advance_amount  ← _deduct_wallet_balance → reconcile top-up → wallet.history 'payment'
CR Receivable (no wallet_id)  = advance_amount  ← advance credit, reconcile với invoice sau
```
Sử dụng `partner.property_account_receivable_id` cho cả hai lines. Journal = `self.journal_id`.

### `_create_wallet_advance` (đặt cọc qua ví)
1. Validate số dư ví (`_check_wallet_balance`)
2. Tạo `account.move` (journal entry) qua `_prepare_wallet_advance_move_vals`
3. `move.action_post()` → `to_wallet._deduct_wallet_balance()` tự động:
   - Reconcile DR (wallet_id) với wallet top-up credit lines
   - Tạo `wallet.history` type `'payment'` (linked vào DR line qua `matched_credit_ids`)
4. Lấy `wallet_history` tự động sinh: `dr_line.matched_credit_ids.wallet_history_id[:1]`
5. Tạo `sale.advance.line` với `transaction_type='deposit'`, `advance_type='wallet'`, `move_id=move.id`, `wallet_history_id=wallet_history.id`

### `_create_cash_bank_advance` (đặt cọc tiền mặt/ngân hàng)
1. Gọi `_prepare_payment_vals` → tạo `account.payment` → post
2. Link payment vào `sale.account_payment_ids`
3. Tạo `sale.advance.line` với `advance_type` lấy từ journal type (`cash/bank`), `transaction_type` từ `payment_type`

### `_prepare_wallet_refund_move_vals` (helper)
Tạo vals cho journal entry hoàn cọc ví:
```
DR Receivable (no wallet_id)   = refund_amount  ← reconcile đóng advance CR line
CR journal.default_account_id  = refund_amount  ← non-receivable, KHÔNG xuất hiện trong invoice outstanding credits
```
**Lý do dùng non-receivable cho CR:** Nếu dùng CR Receivable (wallet_id) → line còn open → xuất hiện trong invoice outstanding credits → khi apply vào invoice → `_partial_deduct_wallet_balance` trigger → ví bị trừ thêm lần 2.

**Fallback account:** Nếu `self.journal_id.default_account_id` không có → tự động tìm journal `cash`/`bank` trong công ty → lấy `default_account_id` của journal đó.

### `_create_wallet_refund` (hoàn cọc qua ví)

**Logic split:**
```
remaining_wallet_advance = wallet_deposited_by_wallet - wallet_refunded

if remaining_wallet_advance > 0:
    refund_amount = min(amount, remaining_wallet_advance)
    topup_amount = amount - refund_amount
    
    1. Tìm advance CR lines còn open (not reconciled, not wallet_id)
    2. Tạo journal entry (DR receivable + CR journal account)
    3. Reconcile DR với advance CR lines → đóng advance accounting
    4. Tạo wallet.history type='refund' trực tiếp (force_done=True)
    5. Tạo sale.advance.line (move_id + wallet_history_id)
    
    if topup_amount > 0:
        → wallet.history type='top-up' trực tiếp → sale.advance.line
else:
    → wallet.history type='top-up' trực tiếp → sale.advance.line
```

**Guard:** Nếu advance CR lines đều đã được reconcile với invoice → raise `UserError` (advance đã dùng, không thể hoàn).

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
```
Journal Entry (advance move):
  DR Receivable (wallet_id)    ← to_wallet._deduct_wallet_balance() → reconcile → wallet.history 'payment' (trừ ví)
  CR Receivable (no wallet_id) ← advance credit, sẽ reconcile với invoice
```
- `wallet.history` được sinh **tự động** bởi `to_wallet` khi post journal entry
- Tracking qua `sale.advance.line` (`move_id` + `wallet_history_id`)
- Không dùng `account_payment_ids`

### Auto-reconcile invoice với wallet advance (`models/account_move.py`)
- Override `action_post` trên `account.move`
- Khi invoice được confirm (out_invoice/out_refund): tìm wallet advance moves của sale order
- Tự động gọi `js_assign_outstanding_line` để reconcile CR advance line với invoice
- Kết quả: invoice amount giảm đúng bằng wallet advance amount

### Hoàn cọc ví
```
Journal Entry (refund move):
  DR Receivable (no wallet_id)   ← reconcile đóng advance CR line (đảo ngược advance)
  CR journal.default_account_id  ← non-receivable (không ảnh hưởng invoice)

wallet.history 'refund' hoặc 'top-up' tạo trực tiếp (force_done=True)
```
- Advance CR line được đóng → không còn xuất hiện trong invoice outstanding credits
- Wallet balance được cộng lại đúng type
- Tracking qua `sale.advance.line` (`move_id` + `wallet_history_id`)

---

## Điểm cần chú ý khi điều chỉnh

1. **`wallet_type_id._check_wallet_history_type`** — mỗi `wallet.type` có cấu hình cho phép loại history nào. Nếu wallet type không cho phép `payment` hoặc `refund` → sẽ raise lỗi. Cần đảm bảo wallet type cấu hình đúng.

2. **`_compute_advance_payment` double-dependency** — method này depend vào cả `account_payment_ids` (từ module gốc) và `advance_line_ids` (module này). Tránh tạo circular dependencies.

3. **`advance_payment_status`** — khi `wallet_amount = 0` (không có khoản ví), trạng thái hoàn toàn do logic gốc quyết định. Module này chỉ can thiệp khi `wallet_amount > 0`.

4. **`journal_id` override `required=False`** — quan trọng để wizard không lỗi khi `is_wallet=True`. Validation journal được thực hiện thủ công trong `make_advance_payment`.

5. **Currency** — `_compute_advance_payment` convert currency của từng CR line sang `sale.currency_id` trước khi cộng. Dùng `line.amount_residual_currency` nếu line có `currency_id`, còn không dùng `amount_residual`.

6. **Journal cho refund** — Journal dùng cho hoàn cọc ví cần có `default_account_id`. Nếu dùng journal type `general` (Hoạt động khác) → cần set tài khoản mặc định, hoặc đảm bảo có journal `cash`/`bank` trong hệ thống để fallback. Khuyến nghị tạo sổ nhật ký riêng cho đặt cọc ví.

7. **`_deduct_wallet_balance` trigger** — DR Receivable (wallet_id) trong advance entry kích hoạt `to_wallet._deduct_wallet_balance()` khi post. Method này gọi `_reconcile_wallet` → tìm wallet top-up credit lines → tạo partial reconcile → `_partial_deduct_wallet_balance` → sinh `wallet.history 'payment'`. Linked vào DR line qua `matched_credit_ids.wallet_history_id`.

8. **Advance CR line phải đóng sau refund** — Nếu không đóng, advance CR vẫn xuất hiện trong invoice outstanding và auto-reconcile (`account_move.py`) sẽ áp dụng nhầm → khách được discount 2 lần. Logic refund đảm bảo reconcile DR refund với advance CR lines còn open.
