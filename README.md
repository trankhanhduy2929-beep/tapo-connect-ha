<p align="center"><img src="custom_components/tapo_camera_local/brand/icon.png" width="128" alt="Tapo Connect" /></p>

# Tapo Connect — Camera Tapo trên Home Assistant

**Phiên bản 0.12.0 · Tapo C260 qua cloud · Push realtime · Tiếng Việt · Có license**

Custom integration đưa camera Tapo C260 lên Home Assistant qua **cloud TP-Link**: đọc thông báo nhận diện (người quen/người lạ/vật nuôi/xe/…), điều khiển ~48 setting (LED, riêng tư, ghi hình, PTZ, preset, lịch ghi, độ nhạy AI, ngày/đêm…). Không cần cùng LAN, không cần Camera Account, không cần cài mồi Tapo Control.

> Bản phát hành này **yêu cầu license key** để thêm entry mới. Xem mục [Đăng ký & kích hoạt](#đăng-ký--kích-hoạt-license).

---

## Mục lục

- [Yêu cầu](#yêu-cầu)
- [Cài đặt](#cài-đặt)
- [Đăng ký & kích hoạt license](#đăng-ký--kích-hoạt-license)
- [Đăng nhập camera Tapo](#đăng-nhập-camera-tapo)
- [Sử dụng](#sử-dụng)
- [Gia hạn / đổi máy / mất key](#gia-hạn--đổi-máy--mất-key)
- [Xử lý lỗi](#xử-lý-lỗi)
- [Bảo mật & giới hạn](#bảo-mật--giới-hạn)

---

## Yêu cầu

- **Home Assistant Core 2026.9.0+** (HA OS / Container / Supervised đều được).
- Camera **Tapo C260** đã đăng ký vào tài khoản Tapo trong app điện thoại.
- HA có **Internet** (để gọi TP-Link cloud và license server).
- Tài khoản **Tapo** (email + mật khẩu dùng trong app Tapo — không phải tài khoản HA, không phải Camera Account).

## Cài đặt

### Cách 1 — HACS (khuyên dùng)

1. Mở **HACS → menu ⋮ → Custom repositories**.
2. Thêm URL: `https://github.com/trankhanhduy2929/tapo-connect-ha` — loại **Integration**.
3. Tìm **Tapo Connect** → **Download** → **khởi động lại Home Assistant**.

### Cách 2 — ZIP thủ công

1. Tải `tapo_connect_<ver>.zip` từ [releases](https://github.com/trankhanhduy2929/tapo-connect-ha/releases).
2. Giải nén vào `<HA_CONFIG>/custom_components/` sao cho đường dẫn cuối là:
   ```
   <HA_CONFIG>/custom_components/tapo_camera_local/manifest.json
   ```
   **Không** lồng hai thư mục `tapo_camera_local`.
3. Khởi động lại Home Assistant.

---

## Đăng ký & kích hoạt license

Bản này **bắt buộc license key** cho mọi entry mới. Một key chỉ gắn với **một** entry camera trên **một** bản cài HA.

### Bước 1 — Mở form License trong HA

1. Vào **Cài đặt → Thiết bị & dịch vụ → Thêm tích hợp → Tapo Connect**.
2. HA sẽ hiện form **License** với ô nhập `license_key` và một **link đăng ký** (chứa identity riêng của bản cài — không phải mật khẩu, không phải token camera).
3. Click link đó (hoặc copy dán vào trình duyệt).

> Link này hiệu lực **30 phút**. Hết hạn thì đóng form và mở lại bước License để lấy link mới. **Không mở nhiều flow cài đặt cùng lúc.**

### Bước 2 — Đăng nhập portal

Trên portal `https://tapo-connect-license.vercel.app`:

1. Nhập **email** của bạn → portal gửi **mã OTP 8 số** về email.
2. Nhập OTP để đăng nhập dashboard.
3. Dashboard cho phép:
   - **Dùng thử (Trial)**: mở link từ HA → hoàn thành chống bot → nhận key miễn phí **24 giờ** (tính từ lúc cấp). Mỗi email/bản cài chỉ được **1 trial**.
   - **Mua gói trả phí**:
     - **7 ngày** — 50.000đ
     - **Vĩnh viễn** — 200.000đ
   - Thanh toán qua **PayOS** (quét QR, giữ nguyên số tiền và nội dung chuyển khoản `RD<mã đơn>`). Backend tự xác minh và cấp key sau khi tiền về.

### Bước 3 — Dán key vào HA

1. Trên dashboard portal, **sao chép license key** (dạng `RD-XXXX-XXXX-…`).
2. Quay lại HA, **dán key vào ô license_key** trong form License → Submit.
3. HA gọi license server để kích hoạt. Thành công → chuyển sang bước đăng nhập Tapo.

> Nếu báo `license_rejected`: key sai/đã hết hạn/đã gắn HA khác.
> Nếu báo `license_unavailable`: mất mạng/server lỗi — thử lại sau 1 phút.

### Bước 4 — Đăng nhập camera Tapo (bước kế tiếp ngay sau license)

Xem mục [Đăng nhập camera Tapo](#đăng-nhập-camera-tapo) bên dưới.

---

## Đăng nhập camera Tapo

Sau khi license được chấp nhận, HA chuyển sang form đăng nhập:

1. Nhập **email + mật khẩu Tapo** (đúng tài khoản đang dùng trong app Tapo).
   - **Không** phải tài khoản HA.
   - **Không** phải Camera Account/RTSP.
   - Mã quốc gia có thể bỏ trống hoặc điền `VN`.
2. Nếu Tapo yêu cầu MFA, kiểm tra **email** để lấy **OTP 6 chữ số** → nhập vào HA.
3. Chọn camera **C260** trong danh sách → **Submit** → xong.

HA tự lưu access token vào `.storage/` (không lưu mật khẩu/OTP). Khi token hết hạn, HA sẽ yêu cầu đăng nhập lại qua nút **Reauth** trên entry.

---

## Sử dụng

### Entity chính

Sau khi thêm entry, vào **Thiết bị → C260 → Thực thể**:

- **Sensors**: loại thông báo gần nhất, thời điểm thông báo gần nhất, người được nhận diện gần nhất, từng người quen có sensor riêng.
- **Binary sensors**: "vừa có thông báo X" — bật **60 giây** khi có thông báo mới rồi tự tắt.
- **Switches**: LED, riêng tư, ghi hình, âm thanh, các thuật toán AI (người/xe/vật nuôi/tiếng động…), theo dõi PTZ, xoay hình, đèn trắng, thông báo Tapo.
- **Numbers**: âm lượng loa/micro (0–100), độ nhạy (1–100).
- **Selects**: ngày/đêm/tự động, chống nhấp nháy 50/60Hz, PTZ preset.
- **Texts**: lịch ghi hình 7 ngày (JSON).
- **Buttons**: đồng bộ ngay, PTZ trái/phải/lên/xuống/dừng, quét ngang/dọc, hiệu chuẩn, khởi động lại, báo động thủ công.

### Automation ví dụ

```yaml
alias: Thông báo người lạ
triggers:
  - trigger: event
    event_type: tapo_camera_local_notification
    event_data:
      tag: stranger
actions:
  - action: notify.mobile_app_dien_thoai_cua_ban
    data:
      title: "Camera phát hiện người lạ"
      message: "{{ trigger.event.data.name }} lúc {{ trigger.event.data.time }}"
```

Các `tag` dùng được: `stranger`, `familiar`, `person`, `pet`, `vehicle`, `motion`, `audio`, `baby_cry`, `bark`, `meow`, `glass_break`, `smoke_alarm`, `tampering`, `intrusion`, `line_crossing`.

### Tốc độ cập nhật

- **Push realtime (thử nghiệm, bật mặc định):** integration giữ một kênh MQTT-over-WebSocket
  tới cloud Tapo; khi camera báo thay đổi, HA cập nhật sensor/setting **ngay lập tức** thay vì
  chờ chu kỳ poll. Tắt/bật trong **Cấu hình → Push realtime**.
- Thông báo: poll **mỗi 5 giây** (chỉnh 5–300 giây) — vẫn chạy làm **dự phòng** khi kênh push lỗi.
- Settings: poll **30 giây**.
- Kênh push là phụ trợ: mọi dữ liệu vẫn đọc qua REST đã xác minh; push lỗi chỉ làm HA chậm hơn,
  không sai và không mất dữ liệu.

### Đổi tùy chọn sau cài

**Cài đặt → Thiết bị & dịch vụ → Tapo Connect → entry camera → Cấu hình**:

- **License / kích hoạt key**: nhập key mới (khi đổi máy, gia hạn, v.v.).
- **Thiết lập camera**: chu kỳ đọc thông báo, URL RTSP nếu muốn stream.

---

## Gia hạn / đổi máy / mất key

| Tình huống | Cách xử lý |
|---|---|
| **Key hết hạn** | Vào portal gia hạn → nhận key mới → vào **Cấu hình → License** trên entry → dán key mới. |
| **Key bị khóa/thu hồi** | Entry sẽ ngừng ở lần kiểm tra tiếp theo (≤ 15 phút). Kiểm tra portal để biết lý do. |
| **Đổi HA / mất `.storage/` / cài lại** | Liên hệ admin portal **Reset** key → key mới sẽ cấp (giữ nguyên thời hạn còn lại) → nhập key mới ở entry. |
| **Mất mạng tạm thời** | HA dùng **lease đã ký** tối đa **24 giờ** từ lần xác minh thành công gần nhất. Không có lease hợp lệ → entry dừng, không cấp quyền giả. |
| **Một key cho nhiều entry** | Không được. Mỗi entry camera cần 1 key riêng. |

---

## Xử lý lỗi

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `license_required` | Chưa nhập key khi thêm mới | Quay lại bước License, lấy link đăng ký, nhận key rồi dán |
| `license_rejected` | Key sai/hết hạn/thu hồi | Kiểm tra lại trên dashboard portal; mua/gia hạn nếu cần |
| `license_unavailable` | Mất mạng/server lỗi | Đợi 1 phút rồi thử lại; HA sẽ tự retry |
| `license_in_use` | Key đã gắn entry khác | Reset key trên portal hoặc dùng key khác |
| `license_configuration` | File `license_policy.json` bị sửa | Cài lại integration từ bản gốc |
| `invalid_auth` | Sai email/mật khẩu Tapo | Kiểm tra lại trong app Tapo trước |
| Không nhận OTP | Tapo chưa yêu cầu MFA / email vào spam | Kiểm tra spam, thử lại sau 1 phút |
| Không thấy camera | C260 chưa đăng ký vào tài khoản Tapo | Mở app Tapo → thêm camera trước |
| `stale_proof` | Đồng hồ HA lệch > 5 phút | Đồng bộ NTP trên host HA |

---

## Bảo mật & giới hạn

- Token phiên Tapo + license key + private identity lưu trong `.storage/` của HA — **bảo vệ quyền truy cập HA và file backup**.
- Không có mật khẩu/OTP/email nào được gửi lên server bên thứ ba ngoài TP-Link và license server chính thức.
- License server chỉ xác minh **key + instance**, không đọc dữ liệu camera, không thu thập email Tapo.
- `cloud_app.json` chứa tham số giao thức chung trích từ APK Tapo — **không phải credentials cá nhân**.
- Đây là **dự án độc lập**, không liên kết TP-Link/Tapo/Home Assistant.

### Chưa có

- Video/ảnh cloud, ảnh face (chưa có API).
- Push realtime, hai chiều âm thanh, xem lại SD/Tapo Care.
- Các model Tapo khác ngoài C260 (chưa kiểm chứng).

---

## Hỗ trợ

- Issues: https://github.com/trankhanhduy2929/tapo-connect-ha/issues
- Portal license: https://tapo-connect-license.vercel.app
- Khi báo lỗi: dùng **Tải xuống chẩn đoán** trên entry (đã che credentials). **Không** đăng mật khẩu, token, license key, email, ảnh mặt công khai.

## Giấy phép & kế thừa

- Schema local kế thừa [pytapo 3.4.19](https://github.com/JurajNyiri/pytapo).
- Tương thích entity với [Tapo Control](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control).
- Giao thức cloud đối chiếu từ APK do chủ thiết bị cung cấp.
