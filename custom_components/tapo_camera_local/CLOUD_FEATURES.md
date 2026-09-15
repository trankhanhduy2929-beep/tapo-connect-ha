# Thông báo và setting camera qua cloud — 0.10.0

Chỉ cần phiên đăng nhập Tapo đã có trong Home Assistant. **Không cần thêm IP,
Camera Account, file JSON, Add-on hoặc cài mồi Tapo Control.** Domain vẫn là
`tapo_camera_local` để giữ entry và entity đã dùng trong automation.

## Nâng cấp từ 0.9.0

1. Sao lưu HA; tải gói `tapo_camera_local_0.10.0.zip`.
2. Thay thư mục `custom_components/tapo_camera_local` bằng thư mục cùng tên trong ZIP.
   Không chồng thêm một lớp `custom_components/custom_components`.
3. Khởi động lại HA. **Không xóa integration, không đăng nhập lại nếu phiên còn hạn.**
4. Mở **Cài đặt → Thiết bị & dịch vụ → Tapo Connect → C260 → Thực thể**.
   HA không tự thêm các thực thể mới vào dashboard do bạn tự bố trí.
5. Lần đầu nâng cấp tải lại lịch sử tối đa 7 ngày để bổ sung các loại thông báo;
   không chạy lại automation cho lịch sử khởi động. Nếu nhiều thông báo, việc tải
   tiếp tục qua nhiều lượt. Tên/thời điểm theo người được lưu riêng để giữ qua restart.

Tên tích hợp có chữ “local API” là tên cũ. **Entry mới chỉ đăng nhập cloud.**
Entry local/companion cũ được giữ tương thích, không tự xóa hoặc chuyển tài khoản.

## Thông báo nào có entity?

Mỗi loại phổ biến có một **sensor thời điểm thông báo gần nhất** và một
**binary sensor “Vừa có thông báo…”**:

| Loại | `tag` dùng trong automation |
|---|---|
| Người quen | `familiar` |
| Người lạ | `stranger` |
| Có người | `person` |
| Vật nuôi | `pet` |
| Xe cộ | `vehicle` |
| Chuyển động | `motion` |
| Âm thanh | `audio` |
| Tiếng trẻ khóc | `baby_cry` |
| Tiếng chó sủa / mèo kêu | `bark` / `meow` |
| Tiếng kính vỡ | `glass_break` |
| Tiếng còi báo khói | `smoke_alarm` |
| Camera bị che hoặc can thiệp | `tampering` |
| Xâm nhập vùng / vượt hàng rào | `intrusion` / `line_crossing` |

Thêm hai sensor tổng: **Loại thông báo camera gần nhất** và **Thời điểm thông báo
camera gần nhất**. Bộ entity nhận diện khuôn mặt 0.9.0, kể cả từng người, giữ nguyên
unique ID. Thông báo người/vật nuôi/xe không ghi đè tên hoặc thời điểm khuôn mặt.

**Quan trọng:** `binary_sensor` bật 60 giây khi nhận **thông báo mới**, sau đó tự tắt,
kể cả khi chưa đến lượt poll tiếp. Đây không phải cảm biến hiện diện liên tục; không
kết luận có người còn đứng trước camera. Thông báo tải lúc khởi động hoặc đến muộn
quá 120 giây chỉ cập nhật lịch sử, không tạo xung/bắn event mới. Hai thông báo cùng
loại liên tiếp trong 60 giây giữ trạng thái On; dùng event nếu muốn xử lý từng lần.
Timestamp là `notification.time`, không phải giờ HA đọc, giờ cập nhật tên hoặc
giờ bắt đầu một video. HA hiển thị theo múi giờ đã cấu hình.

Các cảnh báo khác có parser và tự thêm **sensor thời điểm khi có bản ghi thật**:
thẻ nhớ gần đầy/chưa khởi tạo, lỗi giải mã thẻ, ổ đĩa, quá nhiệt, pin, firmware mới,
lảng vảng, bưu kiện, chuông cửa, chống trộm và thông báo nhiều loại. Không tự tạo
cảnh báo chưa từng nhận hoặc đoán rằng C260 có pin/chuông cửa. Không phân rã
thông báo gộp thành các sự kiện con chưa xác minh.

`unknown` nghĩa là chưa có thông báo loại đó trong dữ liệu đã đọc, **không phải lỗi
đăng nhập**. Khả năng phát hiện tùy model, firmware, cài đặt, lịch và quyền cloud.
Integration đọc lịch sử thông báo giống nguồn app, không thay thế thuật toán AI của camera.

## Các setting trên C260

Entity chỉ xuất hiện khi camera trả về giá trị hợp lệ theo schema đã biết.
Đã đọc trực tiếp được **48 setting** trên C260 thử nghiệm:

| Nhóm | Điều khiển |
|---|---|
| Cơ bản | LED trạng thái, chế độ riêng tư |
| Ghi hình | Bật ghi, ghi vòng lặp, ghi âm; lịch ghi cho 7 ngày |
| Âm thanh | Âm lượng loa/micro, tắt micro, khử nhiễu |
| Hình ảnh | Ngày/đêm, tần số chống nhấp nháy, lật ảnh, sửa méo |
| Theo dõi | Tự theo dõi; theo dõi người, vật nuôi, xe, em bé khi camera hỗ trợ |
| Phát hiện | Bật/tắt và độ nhạy chuyển động, người, vật nuôi, xe, chó sủa, mèo kêu, kính vỡ, che camera, trẻ khóc; nhận diện mặt và vượt hàng rào |
| Thông báo | Bật thông báo, thông báo nâng cao |
| Riêng tư | Bật/tắt vùng che đã có; chưa vẽ/sửa tọa độ vùng |

Tổng trên thiết bị thử: **28 switch, 9 number, 4 select, 7 text**. Các `text` lịch
ghi là điều khiển nâng cao, **tắt mặc định**: mở danh sách thực thể, bỏ lọc và bật
thực thể bị vô hiệu hóa nếu cần. Không nhầm switch “Bật phát hiện người” với
binary sensor “Vừa có thông báo: Người”.

Nút **Làm mới dữ liệu camera** đọc lại setting; nút **Kiểm tra thông báo Tapo ngay**
đọc lịch sử thông báo. Nếu có module PTZ, thêm nút trái/phải/lên/xuống, dừng,
tuần tra ngang/dọc và dừng tuần tra; danh sách preset chỉ hiện khi có preset thật.
Không tự bấm nút khi đăng nhập. Cloud không cung cấp nút reboot, format thẻ nhớ,
reset, hiệu chuẩn hoặc kích còi trong bản này.

Lịch ghi một ngày là chuỗi JSON, ví dụ `["0000-0800:1","0800-2400:2"]`:
`1` ghi liên tục, `2` theo sự kiện; tối đa 10 khoảng, đúng thứ tự và không chồng lấn.
`[]` xóa các khoảng của **ngày được chỉnh**, không thay đổi sáu ngày còn lại.
Không sửa lịch nếu chưa hiểu ý nghĩa của chế độ ghi trên camera của bạn.

## Đồng bộ hai chiều và độ trễ

- **HA → camera:** đọc hiện trạng, gửi đúng một thay đổi, đọc lại xác nhận. Không
  đổi trạng thái HA theo suy đoán. Nếu request thất bại/mất phản hồi, **không tự
  gửi lại write**; entity có thể thành Unavailable đến khi đọc lại được giá trị thật.
- **App/camera → HA:** setting được đọc độc lập mỗi **30 giây**, không dùng chung
  hàng đợi với thông báo. Khi lỗi kết nối, nhịp setting giãn dần tối đa 300 giây và
  trở về 30 giây khi đọc thành công. Query không hỗ trợ được thử lại sau 15 phút.
- **Thông báo:** mặc định **5 giây**, chỉnh **5–300 giây** trong Cấu hình. Sau 10 phút
  không nhận sự kiện mới, giãn ít nhất 30 giây; có thông báo mới sẽ trở về nhịp nhanh.
  Mỗi lượt tối đa 3 trang × 50 bản ghi, tải tiếp nếu còn. Có chống trùng và cửa sổ
  đọc chồng 5 phút để hạn chế mất thông báo đến muộn.
- Setting cloud lỗi không làm mất sensor nhận diện. Camera offline vẫn có thể đọc
  lịch sử cloud; điều khiển camera cần camera online.

Đây vẫn là **polling**, không phải push realtime. Độ trễ tổng gồm camera nhận diện,
TP-Link đưa bản ghi vào API, chu kỳ HA và mạng. Chưa đo được độ trễ đầu-cuối bằng
sự kiện kích trực tiếp trong lần kiểm thử này; không cam kết “báo ngay 0 giây”.

## Automation nhận từng thông báo

Mở **Công cụ nhà phát triển → Sự kiện**, lắng nghe `tapo_camera_local_notification`.
Mỗi sự kiện có `camera_id`, `tag`, `message_type`, `message_id`, `notified_at`,
`time_source`, `source`; `name` chỉ có tên thật nếu thông báo người quen có tên.
Không đưa các giá trị thực tế lên issue công khai.

```yaml
alias: Tapo - Thông báo người lạ
triggers:
  - trigger: event
    event_type: tapo_camera_local_notification
    event_data:
      tag: stranger
conditions: []
actions:
  - action: persistent_notification.create
    data:
      title: Camera Tapo
      message: "Có thông báo người lạ lúc {{ trigger.event.data.notified_at }}"
mode: queued
max: 10
```

Nếu có nhiều camera, thêm `camera_id: "ID_CAMERA_CUA_BAN"` dưới `event_data`.
Đổi `tag` sang `person`, `pet`, `vehicle`… theo bảng. Không dùng state của một
sensor thời điểm để xác định hiện diện. Event cũ `tapo_camera_local_face_notification`
vẫn phát cho người quen/người lạ, không phát cho chuyển động thông thường.

## Kiểm thử và giới hạn thực tế

- Cloud thật → HA Core 2026.9.0 cô lập: tạo entity, tên và thời điểm khớp dữ liệu,
  không replay lúc startup, đọc lần hai/unload thành công. Không triển khai trực
  tiếp lên HA của chủ camera; FFmpeg version dependency được mock, không thử video.
- Đọc được **136 thông báo** trong lượt kiểm tra: **128 có người**, **8 người quen**.
  Các loại người lạ/vật nuôi/xe/âm thanh… đã kiểm thử parser, entity và event bằng
  dữ liệu tổng hợp, **chưa gây đủ từng loại sự kiện trước thiết bị thật**.
- Đọc được 48 setting trong khoảng **1,7 giây** ở một lượt thử; đây không phải SLA.
  Đã đổi LED qua cloud và đọc xác nhận, rồi **khôi phục đúng trạng thái ban đầu**.
  Không tự đổi ghi hình, riêng tư, âm lượng, AI hoặc quay PTZ để thử. Các write
  khác kiểm thử schema/readback bằng transport mô phỏng, chưa xác minh tất cả trên camera.
- `getIntrusionDetectionConfig` bị C260 này từ chối `-40209`; không tạo switch giả.
  Đèn trắng không có giá trị schema được hỗ trợ trong reply nên không tạo switch.
- Chưa đưa toàn bộ màn hình app lên HA: chưa có trình vẽ vùng, quản lý/thêm/xóa
  khuôn mặt, đổi Wi-Fi, cập nhật firmware, playback thẻ nhớ, ảnh face hoặc video cloud.
  Không tạo entity/setting giả cho API chưa có bằng chứng.
- Không có bảo đảm gia hạn cloud mãi mãi. Khi token hết hạn và TP-Link từ chối
  refresh, dùng **Xác thực lại/Cấu hình lại** và nhập OTP nếu được yêu cầu.

## Bảo mật và xử lý lỗi

Không lưu mật khẩu/OTP. Token và lịch sử tên/thời gian được lưu riêng trong
`.storage` của HA với quyền owner-only; bảo vệ HA, backup và quyền người xem
dashboard. Xóa integration xóa đúng session/lịch sử do entry quản lý, không xóa
notification ở TP-Link. `cloud_app.json` là vật liệu giao thức ứng dụng chung,
không phải tài khoản cá nhân; không sửa/xóa file này khỏi gói chạy.

- **Có face nhưng người/vật nuôi/xe Unknown:** bật loại phát hiện/thông báo tương ứng
  trên app; tạo một sự kiện thật và kiểm tra thông báo trong app trước. Sau đó bấm
  **Kiểm tra thông báo Tapo ngay**. Không có bản ghi cloud thì integration không tự tạo.
- **Không thấy setting:** chờ tải nền, mở trang thiết bị và xem Diagnostics. Camera
  phải online; tài khoản chia sẻ/firmware có thể hạn chế quyền. Thử **Làm mới dữ liệu
  camera**. Tên `settings_api_status` trong Diagnostics cho biết query bị từ chối.
- **Bấm setting rồi lỗi:** làm mới và kiểm tra trạng thái thật; tránh bấm liên tục.
  Đặc biệt tắt thông báo/AI/ghi hình/riêng tư có thể làm bạn không nhận sự kiện nữa.
- **Tên entity trên dashboard chưa đổi tiếng Việt:** tên hiển thị dùng ngôn ngữ HA;
  tên bạn tự đặt không bị ghi đè, và `entity_id` cũ không tự đổi khi nâng cấp.
- **Thiếu 7 lịch ghi:** bật các thực thể Text đang Disabled trong trang thiết bị.
- **Báo reauth:** dùng email/mật khẩu **Tapo**, không phải tài khoản HA, RTSP hay admin local.
