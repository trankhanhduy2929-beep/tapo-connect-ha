<p align="center"><img src="custom_components/tapo_camera_local/brand/icon.png" width="128" alt="Tapo Connect" /></p>

# Tapo Connect → Home Assistant

**0.11.2 · Tapo C260 qua cloud · Tiếng Việt**

## Cài đặt nhanh

1. **Giải nén** `tapo_connect_0.11.2.zip` vào `<HA_CONFIG>/custom_components/` để có `custom_components/tapo_camera_local/manifest.json`.
2. **Khởi động lại** Home Assistant.
3. Vào **Cài đặt → Thiết bị & dịch vụ → Thêm tích hợp → Tapo Connect**.
4. Nhập **email + mật khẩu của app Tapo** (KHÔNG phải tài khoản HA/RTSP/admin camera).
5. Nhập **mã OTP** nếu Tapo gửi email yêu cầu.
6. **Chọn camera C260** từ danh sách → xong.

### Cài qua HACS

1. Vào **HACS → Custom repositories → Integration**.
2. Thêm URL: `https://github.com/trankhanhduy2929-beep/tapo-connect-ha`
3. Chọn **Tapo Connect** → **Download** → khởi động lại HA.

## Tính năng

- **15 loại thông báo**: người quen, người lạ, có người, vật nuôi, xe, chuyển động, âm thanh, trẻ khóc, chó sủa, mèo kêu, kính vỡ, còi báo khói, che camera, xâm nhập vùng, vượt hàng rào — mỗi loại có sensor thời điểm + binary sensor xung 60 giây.
- **Tên người quen + thời điểm nhận diện** từ cloud Tapo, mỗi người 1 sensor riêng.
- **48 setting**: LED, riêng tư, ghi hình, âm thanh, ngày/đêm, AI, độ nhạy, thông báo, theo dõi, PTZ, preset, lịch ghi — 28 switch, 9 number, 4 select, 7 text.
- Poll thông báo 5 giây (giãn 30 giây khi yên lặng), settings 30 giây.
- Không cần mật khẩu local, không cần file JSON, không cần cùng LAN.

## License (bản trả phí)

Bản **open-source** này **chưa bật license bắt buộc** — tất cả tính năng hoạt động đầy đủ không cần key.

Nếu bạn nhận được link/bản có `license_policy.json` `enabled=true`:
- Entry **đã tồn tại** trước khi nâng cấp → vẫn chạy bình thường (grandfathered).
- Entry **tạo mới** → cần license key `RD-...` (mua tại portal hoặc dùng trial 24h miễn phí).
- Chi tiết: [LICENSE_GUIDE.md](custom_components/tapo_camera_local/LICENSE_GUIDE.md).

## Yêu cầu

- Home Assistant Core **2026.9.0+**, Python **3.14.2+**.
- Camera Tapo **C260** đã đăng ký cloud (qua app Tapo).
- HA có Internet tới TP-Link cloud.

## Tài liệu chi tiết

- [Sensor, setting, automation, giới hạn](custom_components/tapo_camera_local/CLOUD_FEATURES.md)
- [Đăng nhập, OTP, phiên, MFA](custom_components/tapo_camera_local/CLOUD_LOGIN.md)
- [Thông báo và event automation](custom_components/tapo_camera_local/CLOUD_NOTIFICATIONS.md)
- [Hướng dẫn đầy đủ (tiếng Việt)](custom_components/tapo_camera_local/HUONG_DAN.md)
- [License cho người dùng](custom_components/tapo_camera_local/LICENSE_GUIDE.md)
- [Changelog](CHANGELOG.md)

## Ví dụ automation

```yaml
alias: Thông báo người lạ
trigger:
  - platform: event
    event_type: tapo_camera_local_notification
    event_data:
      tag: stranger
action:
  - service: notify.mobile_app
    data:
      title: "Camera phát hiện người lạ"
      message: "{{ trigger.event.data.name }} lúc {{ trigger.event.data.time }}"
```

Các `tag` khả dụng: `stranger`, `person`, `pet`, `vehicle`, `motion`, `sound`, `baby_cry`, `dog_bark`, `cat_meow`, `glass_break`, `smoke_alarm`, `camera_tamper`, `area_intrusion`, `line_crossing`, `familiar_face`.

## Không phải

- **Không phải** cảm biến hiện diện liên tục — Tapo chỉ gửi khi có sự kiện.
- **Không có** ảnh mặt/video cloud — chỉ metadata (tên + thời điểm).
- **Không** realtime push — poll mỗi 5 giây (đã nhanh nhất có thể qua HTTP API).
- **Không phải** sản phẩm chính thức TP-Link/Tapo hay Home Assistant.

## Bảo mật & pháp lý

- Token phiên + lịch sử lưu trong `.storage/` của HA — bảo vệ quyền truy cập HA và file backup.
- Không có tài khoản/password/OTP nào được gửi lên server bên thứ ba ngoài TP-Link.
- `cloud_app.json` chứa **vật liệu giao thức chung** trích từ APK Tapo (CA, access key, signing secret) — **không phải** credentials cá nhân. Việc phân phối lại file này có thể vi phạm điều khoản sử dụng TP-Link; người dùng tự chịu trách nhiệm pháp lý.
- License key (nếu dùng bản trả phí) được ký Ed25519, kiểm tra định kỳ qua HTTPS, có grace offline ≤ 24 giờ.

## Troubleshooting

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `invalid_auth` | Sai email/mật khẩu Tapo | Kiểm tra lại trong app Tapo trước |
| Không nhận OTP | Tapo chưa yêu cầu MFA cho tài khoản này | Kiểm tra spam folder, thử lại sau 1 phút |
| Không thấy camera | C260 chưa đăng ký cloud | Mở app Tapo → đăng nhập → thêm camera trước |
| `stale_proof` / `invalid_proof` | Đồng hồ HA lệch >5 phút | Đồng bộ NTP trên host chạy HA |
| `license_already_bound` | Key đã kích hoạt trên HA khác | Reset key tại portal → dùng key mới |
| `license_expired` | Hết hạn | Gia hạn tại portal hoặc mua gói mới |

## Phát triển / tự build

```bash
# Lint
ruff check --ignore EXE001 custom_components

# Build release
python -m compileall -q custom_components
```

Tests và scripts build nằm trong repo private của nhà phát hành.

## Giấy phép & kế thừa

- Schema local kế thừa [pytapo](https://github.com/JurajNyiri/pytapo) 3.4.19.
- Tương thích entity với [Tapo Control](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control).
- Cloud protocol đối chiếu từ APK do chủ thiết bị cung cấp.

Dự án độc lập — không liên kết TP-Link/Tapo/Home Assistant.
