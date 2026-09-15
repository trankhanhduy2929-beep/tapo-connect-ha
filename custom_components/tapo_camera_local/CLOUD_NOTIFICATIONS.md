# Tên người và thời điểm từ thông báo Tapo — 0.7.0

> **Đây là hướng dẫn profile cũ của 0.7.0. Bản 0.8.0 đăng nhập email/mật khẩu/OTP ngay trong HA, không yêu cầu khách chép JSON. Xem [CLOUD_LOGIN.md](CLOUD_LOGIN.md).** Entry profile đã có vẫn được giữ; dùng Cấu hình lại để chuyển sang UI. Bản 0.8.0 cũng thay cơ chế `desc` cũ bằng đồng bộ `asc` có mốc lịch sử và trang tiếp nối; giới hạn/cách gia hạn ở tài liệu mới là thông tin hiện hành.

## Kết quả và giới hạn

**Đã đọc được thông báo nhận diện thật của C260 và đưa tên/thời gian vào Home Assistant Core cô lập ngày 13/09/2026.** Không phải tên lấy từ danh bạ mặt rồi gán giờ hiện tại. Chưa cài bản này vào HA đang dùng của chủ camera.

Nguồn là API lịch sử thông báo mà APK Tapo sử dụng: `getAppNotificationByPage`, lọc `familiarFaceDetected`/`unfamiliarFaceDetected` và đúng `deviceId` camera. Tên lấy từ `attachments.personName`, thời gian từ `notification.time`. Đây là **thời điểm thông báo**, chưa chứng minh trùng tuyệt đối với lúc camera bắt đầu nhận diện. HA hiển thị timestamp theo múi giờ đã cấu hình, state chuẩn hóa UTC với độ chính xác giây; event giữ phần mili giây nếu nguồn có.

- Ba sensor chung: **Người được Tapo báo nhận diện gần nhất**, **Thời điểm thông báo nhận diện gần nhất**, **Loại khuôn mặt trong thông báo gần nhất**.
- Tự thêm sensor **Lần Tapo báo nhận diện {tên người} gần nhất** cho từng tên có trong thông báo hợp lệ.
- Thông báo người lạ: loại `stranger`/Người lạ, sensor tên `unknown`; không giữ tên người quen của sự kiện trước. Sensor riêng của người quen giữ lần xuất hiện gần nhất đã biết.
- Poll mỗi **30 giây**, cộng độ trễ server; không phải push realtime. Mỗi lần tối đa 3 trang × 50 thông báo, lấy mới nhất trước. Khi giới hạn bị chạm, thuộc tính `history_truncated` là `true`.
- Mẫu thật không có Face ID/URL ảnh. Bản cloud **không tạo image entity**, không tải ảnh mặt, không đoán Face ID từ tên và không cung cấp cảm biến “người này đang có mặt”.
- Sensor theo người nhóm bằng tên chính xác, vì nguồn chưa có Face ID. Hai người trùng tên bị gộp; đổi tên trên app chỉ thể hiện khi có thông báo với tên mới, có thể tạo sensor mới. Unique ID và entity ID đề xuất dùng mã băm tên, nhưng tên hiển thị và state/attribute vẫn là dữ liệu riêng tư.
- Lịch sử dedupe/last-seen nằm trong RAM. Sau restart/reload chỉ phục hồi phần lịch sử cloud trả về; không bảo đảm giữ đủ người cũ mãi mãi. Không phát event tự động cho lịch sử lúc khởi động. Sau đó chỉ phát message chưa thấy, mới trong 120 giây; thông báo đến quá muộn vẫn cập nhật sensor nhưng không chạy automation cũ.

## Cài nhanh khi đã có profile MFA

**Giữ kết nối camera/control/video đang hoạt động. Thêm một entry cloud riêng, không đổi entry local sang cloud và không cần cài mồi Tapo Control.** Entry này chỉ đọc notification trên cloud, không gửi lệnh đến IP camera.

1. Sao lưu rồi cài ZIP `tapo_camera_local_0.7.0.zip`. Đường dẫn cuối: `<HA_CONFIG>/custom_components/tapo_camera_local/manifest.json`. Restart HA.
2. Copy **riêng** profile do `poc/export_ha_cloud_profile.py` tạo tới `<HA_CONFIG>/tapo_private/tapo-ha-cloud-profile.json`. Trong workspace lab, file đã xuất là `projects/tapo_camera/private/tapo-ha-cloud-profile.json`; **không kèm file này trong ZIP/GitHub**.
3. Đặt quyền thư mục `700`, file `600`. Cả hai phải thuộc UID đang chạy tiến trình HA; chỉ chmod là chưa đủ nếu UID khác. Không dùng symlink/hardlink. Với HA Container, đặt file trong thư mục host đã mount làm `/config`, không đặt bên ngoài volume.

```bash
chmod 700 /config/tapo_private
chmod 600 /config/tapo_private/tapo-ha-cloud-profile.json
```

Các lệnh trên giả định HA config là `/config` và file đã được chuyển an toàn. Chỉ sửa ownership của đúng thư mục/file này khi cần, không chạy `chown -R` hoặc `chmod -R` toàn bộ HA. Không đặt profile trong `www/`, không gửi qua issue/chat công khai, không sửa nội dung token bằng tay.

4. **Cài đặt → Thiết bị & dịch vụ → Thêm tích hợp → Tapo Connect → Nhận diện qua thông báo cloud (hồ sơ MFA riêng)**.
5. Nhập đường dẫn tương đối, **không có `/config/` ở đầu**:

```text
tapo_private/tapo-ha-cloud-profile.json
```

6. Đợi đọc lần đầu, mở thiết bị Tapo C260 để tìm các sensor thông báo. Cloud/local có thể nằm chung thiết bị nếu device ID trùng, nhưng vẫn là hai config entry độc lập. Không nhầm sensor catalog **Tên khuôn mặt** với sensor người được báo nhận diện.
7. Cho camera nhận diện người đã có tên, kiểm tra app có thông báo mới rồi đối chiếu HA sau ít nhất một chu kỳ 30 giây. Bộ kiểm thử không tự thay đổi thiết lập thông báo/nhận diện của camera.

Profile chứa token, vật liệu ký riêng và CA trích từ APK được phép nghiên cứu. Mật khẩu/OTP không cần nhập trong form HA. Profile không phải một token chỉ có quyền đọc: **hãy bảo vệ như thông tin đăng nhập**, dù integration chỉ gọi endpoint đọc.

## Tạo hoặc gia hạn profile

**Từ 0.8.0 hướng dẫn này là legacy.** Người dùng phổ thông hãy làm theo `CLOUD_LOGIN.md`: nhập email/mật khẩu Tapo (và OTP nếu bắt buộc) ngay trong Home Assistant, HA tự lưu phiên. Material giao thức **dùng chung của ứng dụng** đã có trong `cloud_app.json` nên khách không phải cung cấp APK; **profile JSON riêng tư không còn là bước bắt buộc**, và form nhập đường dẫn profile đã bị loại khỏi config flow.

Các bước profile bên dưới chỉ còn dùng để (a) tương thích config entry tạo từ 0.7.0 — mở entry rồi chọn **Configure/Cấu hình lại** để HA tự chuyển sang kho phiên bản do HA quản lý, hoặc (b) nghiên cứu trên máy lab. Công cụ exporter hiện tự chọn khi tài khoản có **đúng một C260**; nếu có nhiều C260 thì dừng, không đoán camera.

Các bước dưới chạy trên **máy lab**, không phải HA OS. Dùng môi trường Python có `poc/requirements-ha-test.txt`, thư mục `private/` quyền `700`. Tài khoản nhập trong file `private/tapo-online-account.ini` quyền `600`:

```ini
[tapo_cloud]
email = EMAIL_TAPO_CUA_BAN
password = MAT_KHAU_TAPO_CUA_BAN
region_code = VN
```

Nếu đã có session xác minh còn hiệu lực, **bỏ qua gửi OTP**, chạy từ `projects/tapo_camera`:

```bash
.ha-test-venv/bin/python poc/export_ha_cloud_profile.py \
  --credentials-file private/tapo-online-account.ini \
  --state-file private/tapo-mfa-session.json \
  --apktool-dir ../../analysis/apktool_base \
  --output private/tapo-ha-cloud-profile-new.json
```

Thay đường dẫn APKtool nếu cấu trúc lab khác. Exporter chỉ đọc thiết bị, không sửa camera, không ghi đè profile đã có. Chuyển file mới riêng sang HA và dùng **menu entry cloud → Cấu hình lại** để chọn đường dẫn mới; không cần xóa entry/sensor.

Nếu session hết hạn, làm luồng email MFA mới có chủ tài khoản tham gia; chọn các tên file mới, không ghi đè lịch sử trước:

```bash
.ha-test-venv/bin/python poc/cloud_mfa.py start \
  --credentials-file private/tapo-online-account.ini \
  --apktool-dir ../../analysis/apktool_base \
  --state-file private/tapo-mfa-session-new.json \
  --code-file private/tapo-mfa-code-new.ini \
  --output private/mfa-start-new.json
```

Khi report có `mfa_status: waiting_code`, điền OTP vào `[mfa] code =` trong file mã riêng. Không nhập mã vào command line, không chạy lại `start` để nhận thêm email. Sau đó:

```bash
.ha-test-venv/bin/python poc/cloud_mfa.py verify \
  --credentials-file private/tapo-online-account.ini \
  --apktool-dir ../../analysis/apktool_base \
  --state-file private/tapo-mfa-session-new.json \
  --code-file private/tapo-mfa-code-new.ini \
  --output private/mfa-verify-new.json
```

Chỉ export bằng state mới khi report xác nhận `authenticated: true`. Công cụ không tắt MFA, không đánh dấu máy là thiết bị tin cậy, không gửi lại xác minh không rõ kết quả. Runtime HA không tự login/refresh token, nên cần quy trình này khi phiên hết hạn; chưa biết chính sách thời hạn session của TP-Link để cam kết số ngày.

## Automation

Event cloud là **`tapo_camera_local_face_notification`**, khác event tracking local `tapo_camera_local_face_recognized`. Dữ liệu có `camera_id`, `message_id`, `name`, `tag`, `face_id` (có thể `null`), `notified_at`, `source`, `time_source`.

Ví dụ này tạo thông báo HA có dữ liệu người; chỉ dùng trên tài khoản/dashboard được phép xem. Nếu có nhiều camera, thêm điều kiện theo `camera_id` riêng của bạn, không đưa ID thật lên GitHub:

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

Nếu cùng người được nhận diện lần nữa, sensor tên không nhất thiết thay state. Nên trigger bằng event hoặc sensor timestamp của người đó, không chỉ dựa vào việc tên đổi. Không dùng automation nhận diện này để tự mở khóa/cửa nếu chưa có các bước xác thực và kiểm soát an toàn phù hợp.

## Lỗi thường gặp và quyền riêng tư

| Hiện tượng | Cách kiểm tra |
|---|---|
| Không có menu cloud | Kiểm tra manifest `0.7.0`, đúng một cấp thư mục, restart HA và tải lại trang |
| Không đọc được hồ sơ | Đường dẫn tương đối; UID của tiến trình HA; thư mục `700`, file `600`; file thường không link; JSON xuất bằng exporter |
| Phiên cloud bị từ chối | Làm MFA/export mới, dùng Cấu hình lại; không thử lại mật khẩu liên tục |
| Sensor unknown | Chưa có thông báo face hợp lệ cho camera hoặc thông báo là người lạ/không có tên; không lấy catalog giả làm event |
| Sensor unavailable | Cloud mất kết nối/phiên hết hạn; local entry vẫn hoạt động độc lập nếu camera truy cập được |
| Tên đã đổi trong app nhưng sensor cũ còn | Chờ thông báo với tên mới; cloud không ánh xạ được danh bạ Face ID nên không tự sửa lịch sử người cũ |
| Sensor thời điểm local vẫn không có | Đó là API tracking khác. Dùng các sensor có chữ **Tapo báo**/**thông báo**, không chờ endpoint local `-40209` tự được sửa |
| Ảnh mặt chưa xuất hiện | Mẫu cloud không trả URL/ảnh, API local JSON bị từ chối. Không dùng ảnh toàn cảnh thay ảnh khuôn mặt |

Cloud HTTPS bật kiểm tra CA/hostname, chỉ tới host TP-Link được giới hạn, không theo redirect hoặc proxy môi trường, response tối đa 2 MiB. Không xóa/đánh dấu thông báo đã đọc, không đăng ký push token, không đổi camera. Chẩn đoán cloud chỉ xuất trạng thái/số lượng, không xuất token/tên/ID mặt/thời gian thật. Tuy nhiên HA Recorder, event bus và backup **có thể lưu tên/thời gian**; giới hạn người có quyền truy cập, bảo vệ backup và không bật debug HTTP thô.

Smoke test `poc/live_notification_ha.py` dùng HTTP cloud thật, HA Core/entity thật, thư mục HA tạm riêng, không truy cập HA người dùng. Dependency nhận dạng phiên bản FFmpeg được mock vì không kiểm thử video; không mock thông báo hoặc sensor. Kết quả báo cáo chỉ là counts/booleans. Phát RTSP, ảnh face và độ ổn định cloud nhiều ngày chưa được kiểm thử.
