# Đăng nhập Tapo ngay trong Home Assistant — 0.10.0

**Khách chỉ cần tài khoản Tapo, mã xác minh nếu Tapo yêu cầu, rồi chọn camera. Không chép JSON, không điền token, không cài mồi Tapo Control.** Home Assistant tự lưu phiên, tạo sensor và setting. Danh sách mới và automation: [CLOUD_FEATURES.md](CLOUD_FEATURES.md).

## Cài đặt trong 3 bước

1. Cài `tapo_camera_local_0.10.0.zip` vào `<HA_CONFIG>/custom_components/`, sao cho có đúng `<HA_CONFIG>/custom_components/tapo_camera_local/manifest.json`. Restart HA. Nếu đã có entry 0.9.0, giữ entry đó; chỉ đăng nhập lại khi HA báo hết phiên. Giữ nguyên kết nối local/video đang chạy.
2. **Cài đặt → Thiết bị & dịch vụ → Thêm tích hợp → Tapo Connect → Đăng nhập Tapo cloud (tên người và thời gian)**. Nhập **email và mật khẩu đang dùng trong ứng dụng Tapo**. Không dùng tài khoản đăng nhập HA hoặc Camera Account/RTSP. Mã quốc gia là tùy chọn, có thể bỏ trống hoặc nhập `VN`.
3. Nếu được hỏi, nhập OTP 6 chữ số từ email Tapo ngay trong form HA. Sau đó chọn **C260** trong danh sách và hoàn tất. HA tự lưu phiên, đọc cloud và thêm sensor.

Khi bấm đăng nhập, bạn cho phép gửi **một** email xác minh nếu tài khoản yêu cầu MFA. Integration không tắt/bỏ qua MFA, không tự đọc email của bạn và không đánh dấu HA là thiết bị tin cậy. Giữ nguyên các số 0 ở đầu OTP; không gửi mã lên chat/issue. Nếu server từ chối hoặc yêu cầu chờ, không bấm lặp liên tục.

Nếu chỉ có một C260, camera đó được chọn sẵn nhưng vẫn cần xác nhận. Tài khoản nhiều C260 có thể chọn đúng thiết bị; model khác chưa xác minh. Đăng nhập chỉ đọc dữ liệu; lệnh đổi setting chỉ gửi khi bạn chủ động điều khiển entity. Không đăng ký push token hay đánh dấu/xóa thông báo.

## HA tự xử lý gì?

- Tìm máy chủ TP-Link theo vùng; kiểm tra tài khoản bị khóa trước khi gửi mật khẩu.
- Đăng nhập, gửi yêu cầu mã email khi cần, xác minh mã, đọc danh sách camera và kiểm tra notification của camera đã chọn.
- **Không lưu mật khẩu hoặc OTP.** Lưu access/refresh token bằng kho riêng của HA trong `.storage/`, file owner-only. Người dùng không cần mở, sửa, cấp chmod hoặc chuyển file này.
- Tái sử dụng phiên qua restart, đọc dữ liệu ngoài event loop, giữ cloud riêng với control/video local.
- Khi token bị từ chối, thử gia hạn một lần bằng refresh token, lưu token mới trước khi đọc tiếp. Nếu gia hạn bị từ chối hoặc không rõ kết quả do lỗi mạng, HA yêu cầu **đăng nhập lại ngay trên giao diện**. Không gửi lại mật khẩu/OTP hàng loạt.
- Xóa integration sẽ xóa đúng bản lưu phiên do entry đó quản lý, không xóa file của integration khác hoặc tự thu hồi phiên app điện thoại.

**Giới hạn đã kiểm thử:** nhánh gia hạn tự động và chống gửi trùng đã qua kiểm thử mô phỏng; yêu cầu gia hạn bằng session thật hiện có bị TP-Link từ chối. Vì vậy **chưa cam kết đăng nhập một lần dùng vĩnh viễn**, không cam kết chu kỳ hết hạn hoặc gia hạn thành công với mọi tài khoản. Đăng nhập lại qua UI vẫn không cần JSON. Mã MFA do chủ tài khoản nhập là bước không thể tự bỏ qua.

## Sensor và đồng bộ

- **Người được Tapo báo nhận diện gần nhất** — tên từ thông báo thật.
- **Thời điểm thông báo nhận diện gần nhất** — `notification.time`, không phải giờ poll hoặc giờ cập nhật hồ sơ.
- **Loại khuôn mặt trong thông báo gần nhất** — người quen/người lạ.
- **Lần Tapo báo nhận diện {tên người} gần nhất** — tự thêm cho từng tên có trong lịch sử hợp lệ.

Thời gian là giờ thông báo phía cloud, chưa chứng minh trùng tuyệt đối thời điểm camera bắt đầu nhận diện. HA hiển thị theo múi giờ của HA, timestamp state chuẩn hóa tới giây. Người lạ không giữ tên người quen cũ; tên `unknown` nếu nguồn không cung cấp tên. Không suy ra “người đó đang có mặt”.

**Tốc độ cập nhật:** mặc định đọc thông báo **mỗi 5 giây**; có sự kiện mới hoặc còn trang dở thì giữ nhịp nhanh, yên lặng **10 phút** sẽ nới ít nhất **30 giây**. Đổi trong **Cấu hình → Chu kỳ đọc thông báo cloud** (5–300 giây). Nút **Kiểm tra thông báo Tapo ngay** ép đọc tức thì. Setting camera chạy độc lập mỗi 30 giây, cập nhật sau khi đọc xác nhận một lệnh điều khiển.

**Integration chưa triển khai kênh push đã kiểm chứng.** Đây là polling; độ trễ còn gồm camera nhận diện, TP-Link công bố bản ghi, hàng đợi và mạng. Đặt 5 giây giảm thời gian chờ poll nhưng không bảo đảm thông báo tức thì.

Lượt đầu đọc lịch sử tối đa 7 ngày theo `asc` như luồng app; mỗi lượt tối đa 3 trang × 50 thông báo, tiếp tục trang còn dở ở lượt sau, nên tài khoản nhiều thông báo có thể cần vài chu kỳ để bắt kịp. Sau đó đọc tăng dần theo **mốc (watermark)** — 0.9.0 lưu mốc này trong file phiên của HA nên **khởi động lại không tải lại cả 7 ngày**; vẫn đọc chồng 5 phút chống trễ và dedupe theo message ID. Thông báo đến muộn hơn cửa sổ chồng chưa được bảo đảm.

Không phát lại automation trong toàn bộ lượt tải lịch sử đầu, kể cả nhiều trang/lượt; sau đó chỉ phát message chưa thấy và mới trong 120 giây. Từ 0.10.0 lịch sử mới nhất theo loại/người được lưu riêng trong HA và khôi phục không replay. Nâng cấp lần đầu tải lại tối đa 7 ngày để thêm các loại thông báo. Không lưu toàn bộ lịch sử vô hạn.

**Ảnh khuôn mặt chưa được triển khai.** Các lượt thử cũ không có URL ảnh trong thông báo, catalog cloud rỗng và truy vấn ảnh local bị từ chối. Kênh P2P `get_face` thấy trong APK chưa được kiểm chứng. Các kết quả này không chứng minh ảnh là bất khả thi hoặc mua thêm dịch vụ sẽ lấy được ảnh; bản này không tạo image entity hay dùng ảnh toàn cảnh thay thế.

Không tự ánh xạ tên thành Face ID. Hai người trùng tên bị gộp trong sensor theo người; đổi tên trên app có thể tạo sensor mới khi có thông báo mới. Entity ID dùng mã băm tên, nhưng tên hiển thị/state/attributes vẫn là dữ liệu riêng tư.

## Automation mẫu

```yaml
alias: Tapo báo nhận diện người quen
triggers:
  - trigger: event
    event_type: tapo_camera_local_face_notification
conditions:
  - condition: template
    value_template: >-
      {{ trigger.event.data.get('tag') == 'familiar'
         and trigger.event.data.get('name') not in [none, ''] }}
actions:
  - action: persistent_notification.create
    data:
      title: Camera Tapo
      message: >-
        {{ trigger.event.data.name }} —
        {{ as_local(as_datetime(trigger.event.data.notified_at)) }}
mode: queued
```

Nếu có nhiều camera, lọc thêm `camera_id` thực của bạn; không đăng ID/tên/timestamp thật công khai. Cùng người nhận diện nhiều lần không làm state tên đổi, nên dùng event hoặc sensor timestamp, không chỉ dùng sensor tên. Không dùng nhận diện mặt làm điều kiện duy nhất để mở khóa/cửa.

## Nâng cấp từ 0.7.0 dùng profile

1. Cập nhật integration và restart; entry profile cũ vẫn đọc được, không bị xóa tự động.
2. Trên **entry cloud cũ**, chọn menu ba chấm → **Cấu hình lại**. Đăng nhập Tapo/OTP và chọn đúng camera cũ.
3. HA giữ nguyên entry/device/sensor ID, chuyển sang kho phiên HA tự quản lý. Không cần thêm lại sensor hoặc sửa automation.
4. Sau khi xác nhận đã hoạt động, bạn có thể tự sao lưu/gỡ profile JSON cũ vì entry không dùng nữa. Integration không tự xóa file do người dùng cung cấp. Không cần thay đổi hoặc gỡ local/Tapo Control.

Nếu chọn camera khác trong lúc cấu hình lại, HA từ chối và giữ nguyên cấu hình cũ. Tạo entry mới nếu thật sự muốn thêm camera khác.

## Xử lý lỗi

| Hiện tượng | Cách xử lý |
|---|---|
| Không có form email/mật khẩu | Kiểm tra manifest `0.9.0`, đúng thư mục, restart HA và tải lại trang |
| Sai tài khoản/khóa tạm | Dùng email/mật khẩu ứng dụng Tapo, không phải Camera Account; chờ server cho phép trước khi thử lại |
| Chưa nhận OTP | Kiểm tra spam/email đúng tài khoản; không gửi yêu cầu liên tục. Không có nút tự resend trong vòng lặp |
| OTP sai/hết hạn | Bắt đầu đăng nhập lại. Mã hợp lệ về định dạng chỉ gửi một lần để không phát lại yêu cầu không rõ kết quả |
| Không thấy camera | Tài khoản phải có C260, không tự đoán ID hoặc truy cập camera tài khoản khác |
| Không lưu được phiên | Kiểm tra dung lượng và quyền thư mục cấu hình HA, thử lại bước chọn camera; không cần đăng nhập lại nếu phiên bước này còn |
| Session hết hạn | Làm theo yêu cầu xác thực lại của HA; không export/chuyển token bằng tay |
| Sensor trống ngay sau cài | Chờ đồng bộ lịch sử; xác nhận app có thông báo face có tên. Không dùng tên catalog/giờ hiện tại để giả sự kiện |
| Control/video không xuất hiện ở entry cloud | Đây là entry chỉ đọc thông báo. Giữ/thêm entry standalone cho controls/RTSP nếu cần |

## Bảo mật và phát hành cho khách

- Credential của mỗi khách chỉ gửi bằng HTTPS có kiểm tra CA/hostname tới máy chủ TP-Link được giới hạn. Không qua server trung gian của người phát hành; không đưa token/mật khẩu/OTP vào ZIP/GitHub, log chẩn đoán hoặc form result.
- `cloud_app.json` **đi kèm component** là tham số ứng dụng chung/CA/vật liệu ký trích từ APK được phép phân tích, **không phải profile đăng nhập riêng của khách**. Không xóa file này khỏi gói rồi yêu cầu khách tự điền lại. Nó không chứa email, access/refresh token, OTP hoặc ID camera. Vật liệu ký app vẫn là dữ liệu nhạy cảm của giao thức; không coi đây là OAuth/API công khai chính thức của TP-Link. Người phát hành cần xem xét quyền phân phối tài liệu/vật liệu giao thức; báo cáo không chép giá trị khóa.
- Kho `.storage/`/backup **không được integration mã hóa bằng khóa riêng**. Quyền file hạn chế không bảo vệ khỏi quản trị viên HA hoặc người có quyền backup. Bảo vệ HA, backup, Recorder/event bus và người được xem dashboard vì chúng có thể lưu tên/thời gian.
- Tải diagnostics chỉ có trạng thái/số lượng; không bật debug HTTP/raw payload khi chia sẻ log. Không upload thư mục `.storage`, profile legacy hoặc ảnh mặt lên issue.

## Kiểm thử

Luồng form email → OTP → chọn camera → lưu phiên → load HA, reauth/migration/unload/remove và refresh được kiểm thử bằng HA Core thật với HTTP dữ liệu tổng hợp. Lượt kiểm thử cloud thật dùng session MFA đã được chủ tài khoản xác minh trước đó, cấu hình giao thức đóng gói và kho HA tự quản lý: **8 notification, 1 tên phân biệt, 4 sensor khớp dữ liệu**, đọc lại thành công. Không tự gửi thêm email OTP khi chạy smoke test. Phiên bản FFmpeg được mock vì không kiểm thử video; cloud HTTP và entity không mock. Chưa thực hiện một lần đăng nhập/OTP mới end-to-end qua UI trên HA của khách, chưa kiểm thử ổn định nhiều ngày, ảnh mặt hoặc RTSP thật.
