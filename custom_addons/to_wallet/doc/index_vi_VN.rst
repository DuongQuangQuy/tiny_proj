Cài đặt
=======
1. Truy cập **Ứng dụng**.
2. Tìm từ khóa *to_wallet*.
3. Ấn **Cài đặt**.

Hướng dẫn sử dụng
=================

**Video hướng dẫn:** `Ví điện tử <https://youtu.be/UXRZWelfB1Y>`_

Khái niệm
---------

Khi sử dụng mô-đun này, bạn cần tìm hiểu một số khái niệm sau:

- Ví điện tử: là một tài khoản Online có khả năng thanh toán trực tuyến các hóa đơn, mua sắm... Để sử dụng ví, bạn sẽ cần nạp tiền vào ví và tiến hành các giao dịch thanh toán trên.
- Là hoạt động ví điện tử: Là việc đánh dấu cho hệ thống biết giao dịch nào cần phải thực hiện qua ví điện tử.
- Giá trị nạp ví: Là giá trị tiền được nạp vào ví điện tử.
- Giao dịch thanh toán online: Giao dịch thanh toán sử dụng các nhà cung cấp dịch vụ thanh toán như Momo, VNpay, Paypal, Chuyển tiền ngân hàng,...

Luồng hoạt động
---------------

**1. Thiết lập sản phẩm trả bằng ví điện tử**

Tại giao diện Sản phẩm, bạn tích chọn **Thanh toán bằng ví** tại tab Kế toán.

.. image:: 01-san-pham-thanh-toan-bang-vi-Viindoo.vi.jpg
   :alt: Sản phẩm thanh toán bằng ví điện tử Viindoo
   :height: 480
   :width: 1100

**Lưu ý:** Bạn cần cài đặt module `to_account_accountant <https://viindoo.com/vi/apps/app/17.0/to_account_accountant>`_ để lựa chọn tính năng này.

**2. Nạp tiền vào ví điện tử**

Truy cập **Kế toán > Khách hàng > Thanh toán**, ấn **Tạo** để ghi nhận `thanh toán <https://viindoo.com/documentation/16.0/vi/applications/finance/accounting-and-invoicing/account-receivables/customer-payments/how-to-create-customer-payment-in-viindoo-accounting.html>`_ nạp tiền của khách hàng. Lưu ý tích chọn
**Nạp/Rút tiền trong Ví** và điền giá trị cần nạp vào ví của khách hàng.

.. image:: 02-nap-tien-vao-vi-Viindoo.vi.jpg
   :alt: Nạp tiền vào ví điện tử Viindoo
   :height: 470
   :width: 1100

Ấn **Xác nhận** để xác nhận thanh toán. Tại giao diện hồ sơ khách hàng, bạn có thể theo dõi số tiền đã nạp vào ví tại *tab Ví*.

.. image:: 03-vi-dien-tu-khach-hang-Viindoo.vi.jpg
   :alt: Ví điện tử của khách hàng
   :height: 400
   :width: 1100

**Lưu ý:** Nếu bạn kích hoạt `đa tiền tệ <https://viindoo.com/documentation/16.0/vi/applications/finance/accounting-and-invoicing/multi-currencies/how-to-configure-a-multi-currencies-system.html>`_, hệ thống sẽ ghi nhận giá trị ví điện tử với giá trị ngoại tệ.

**3. Khách hàng theo dõi ví điện tử**

Khi được cấp `quyền truy cập cổng thông tin <https://viindoo.com/documentation/16.0/vi/applications/sales/sales/advanced-topics/granting-portal-access-to-customers.html>`_ vào hệ thống, khách hàng có thể theo dõi ví điện tử bằng cách truy cập tại mục *Ví* tại tài khoản cá nhân.

.. image:: 11-Theo-doi-vi-dien-tu-Viindoo.vi.jpg
   :alt: Theo dõi ví điện tử
   :height: 290
   :width: 1100

Tại đây, bạn có thể ấn **Nạp tiền** để nạp thêm tiền vào ví điện tử của mình. Lưu ý, việc nạp tiền chỉ áp dụng trong trường hợp bạn đã từng nạp tiền trong ví qua các nhà cung cấp dịch vụ thanh toán như `Momo <https://viindoo.com/documentation/16.0/vi/applications/finance/accounting-and-invoicing/account-receivables/customer-payments/how-to-make-a-payment-with-momo.html>`_, `VNpay <https://viindoo.com/documentation/16.0/vi/applications/finance/accounting-and-invoicing/account-receivables/customer-payments/how-to-make-a-payment-with-vnpay.html>`_, `Paypal <https://viindoo.com/documentation/16.0/vi/applications/finance/accounting-and-invoicing/account-receivables/customer-payments/how-to-make-a-payment-with-paypal.html>`_, Chuyển tiền ngân hàng, v.v.

**4. Tạo đơn bán**

Truy cập **Bán hàng > Đơn bán > Báo giá**, ấn **Tạo** để tạo mới báo giá mới tại ứng dụng quản lý bán hàng. 

.. image:: 04-tao-don-ban-Viindoo.vi.jpg
   :alt: Tạo đơn bán Viindoo
   :height: 560
   :width: 1100

Sau khi khách hàng đồng ý, ấn **Xác nhận** để chuyển báo giá thành đơn bán.

**5. Tạo hóa đơn và thanh toán bằng ví điện tử**

Tại giao diện đơn bán, ấn **Tạo hóa đơn** để tạo hóa đơn cho đơn bán này.

.. image:: 05-tao-hoa-don-Viindoo.vi.jpg
   :alt: Tạo hóa đơn tại phần mềm kế toán Viindoo
   :height: 560
   :width: 1100

Tại đây, bạn tích chọn **Là hoạt động Ví điện tử** tại tab Chi tiết hóa đơn. Ấn **Xác nhận** để vào sổ hóa đơn này.

.. image:: 06-vao-so-hoa-don.vi.jpg
   :alt: Vào sổ hóa đơn Viindoo
   :height: 560
   :width: 1100

Lúc này hệ thống hiển thị thông báo có một khoản thanh toán dư đối với khách hàng này. Ấn **Thêm** tại mục *Có tồn đọng* để sử dụng số tiền trong Ví điện tử của khách hàng này. 

.. image:: 07-su-dung-tien-trong-vi-Viindoo.vi.jpg
   :alt: Sử dụng tiền trong ví
   :height: 580
   :width: 1100

Trong trường hợp số tiền trong ví không đủ để thanh toán hết hóa đơn, bạn ấn **Ghi nhận thanh toán** để ghi nhận phần thanh toán còn lại.

.. image:: 08-ghi-nhan-thanh-toan-Viindoo.vi.jpg
   :alt: Ghi nhận thanh toán Viindoo
   :height: 420
   :width: 1100

.. image:: 09-xac-nhanh-thanh-toan-Viindoo.vi.jpg
   :alt: Xác nhận thanh toán Viindoo
   :height: 380
   :width: 1100

.. image:: 10-hoa-don-da-thanh-toan-Viindoo.vi.jpg
   :alt: Hóa đơn đã thanh toán
   :height: 410
   :width: 1100

**Ghi chú:** Trong trường hợp công ty nạp tiền vào ví điện tử, các các nhân thuộc công ty có thể sử dụng thanh toán bằng ví điện tử của công ty.

Lúc này bạn thực hiện `tạo sao kê <https://viindoo.com/documentation/16.0/vi/applications/finance/accounting-and-invoicing/bank-cash/bank-reconciliation/manage-bank-statements.html>`_ và thực hiện `đối soát sao kê <https://viindoo.com/documentation/16.0/vi/applications/finance/accounting-and-invoicing/bank-cash/bank-reconciliation/steps-in-the-bank-reconciliation-process.html>`_.
