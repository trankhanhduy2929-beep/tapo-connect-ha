# License Tapo Connect trong Home Assistant

## Nâng cấp an toàn

Sao lưu Home Assistant trước khi thay component. Không xóa entry camera cũ.
Giữ nguyên `custom_components/tapo_camera_local`; khởi động lại HA sau khi thay file.
Domain, unique ID, tài khoản Tapo, sensor và setting hiện có không đổi.

Gói source chưa cấu hình website có `license_policy.json` với `enabled=false`.
Đây là **bản nâng cấp tương thích**, không phải bản thương mại đã bật chặn license.
Nhà phát hành phải deploy server và tạo bản `*_licensed.zip` bằng script publisher.
Không tự điền một server hoặc public key bất kỳ để dùng key của nhà phát hành khác.

## Khách mới

1. Cài bản có license của nhà phát hành, chọn Thêm tích hợp → Tapo Connect.
2. Mở link **Đăng ký / TEST 1 ngày / mua license** ngay trong form License.
   Link chứa public identity có chữ ký, không chứa mật khẩu Tapo hay private key.
3. Đăng nhập website bằng email → nhận mã 8 số → xác minh.
4. Trial: mở link từ HA, hoàn thành chống bot, nhận key. Mỗi email/bản cài chỉ một
   trial; hiệu lực **24 giờ từ lúc cấp**, không phải từ lần dán key.
5. Gói trả phí: 7 ngày 50.000đ hoặc vĩnh viễn 200.000đ. Tạo đơn, quét QR PayOS,
   giữ nguyên số tiền và nội dung riêng `RD<mã đơn>`. Backend xác minh rồi tự cấp key.
6. Sao chép key trong dashboard, dán vào form HA. Sau đó đăng nhập Tapo như cũ.
   Gói trả phí tính hạn từ lần kích hoạt đầu; một key dùng cho một entry custom.

Link trial hiệu lực 30 phút; nếu hết hạn, mở lại bước License để lấy link mới.
Không mở nhiều flow cài mới cùng lúc. Khi hủy và mở lại, HA giữ draft identity để
không làm mất trial/key đã nhận. Nếu đã có entry camera, dùng mục Cấu hình của entry.

## Camera đã có

Cài đặt → Thiết bị & dịch vụ → entry camera → Cấu hình:

- **License / kích hoạt key**: nhập key mới, xem link dashboard.
- **Thiết lập camera hiện có**: vẫn điều chỉnh chu kỳ cloud/RTSP cũ như trước.

Mặc định publisher giữ entry từ phiên bản cũ không cần key (`grandfather_existing`).
Khi chủ động nhập key, entry đó chuyển sang kiểm tra license. Đăng nhập lại Tapo,
reload hoặc đổi options không xóa license đã gắn. Không tự xóa metadata license.

## Mất mạng / hết hạn / đổi máy

- Server kiểm tra định kỳ 15 phút, độc lập polling thông báo 5 giây và settings 30 giây.
- Nếu server/mạng lỗi tạm thời, dùng lease đã ký tối đa 24 giờ kể từ lần xác minh
  thành công, không vượt ngày hết hạn. Không có lease hợp lệ thì không cấp quyền giả.
- Key bị khóa/thu hồi: ngừng entry khi nhận từ chối; nếu HA offline thì chưa thể
  nhận lệnh khóa cho tới lần online hoặc hết lease. Sai số lịch kiểm tra tối đa 30 giây.
- Hết quyền: entity của entry đó không hoạt động; tài khoản, cấu hình và lịch sử camera
  không bị xóa. Nhập key hợp lệ trong Options để HA nạp lại.
- Đổi HA/mất `.storage`: nhờ admin **Reset**. Reset đổi key để máy cũ không giành
  kích hoạt lại; giữ nguyên thời hạn. Lấy key mới trên dashboard. Trial không reset.
- Backup HA chứa private identity/key/license. Bảo vệ file backup và quyền admin HA.
  Gỡ/re-add cùng HA giữ private license store để phục hồi; không tự nhả key trên server.

## Dành cho nhà phát hành

Nguồn 0.11.2 đã được kiểm chứng với portal đang chạy (đăng nhập OTP, trial, kích hoạt
bằng client Python của chính custom, lease ký, một key một bản cài, đơn PayOS thật rồi
hủy, webhook giả mạo/uns paid bị từ chối, admin issue/block/unblock/reset). Chi tiết:
`projects/tapo_connect_license/docs/PAYOS_SETUP_VI.md`.

Không dùng YAML để đưa PayOS secret vào HA. Chỉ có HTTPS URL và **public key** trong
`license_policy.json`. Secrets server phải giữ trên Vercel/database.

```bash
python scripts/publish_licensed.py \
  --server https://license.example.com \
  --public-key PUBLIC_KEY_43_KY_TU_TU_ENV_KEYS \
  --output dist_licensed
```

Script phải truy cập được server thật `/api/license/info` và xác nhận public key
đúng. Nó chỉ sửa bản copy để đóng ZIP, không thay source/camera đang chạy.
Không có Add-on daemon trong project này; nếu tích hợp vào một add-on có sẵn,
xem `poc/license_addon_adapter.py` và tài liệu API của license server.

**Giới hạn:** mã nguồn mở và backup có thể bị chủ máy sửa/clone. Server ngăn key
khác instance/private key, nhưng không phải DRM phần cứng chống sao chép tuyệt đối.
Camera vẫn chỉ có các tính năng đã xác minh ở 0.10.0, không bổ sung video/face image.
