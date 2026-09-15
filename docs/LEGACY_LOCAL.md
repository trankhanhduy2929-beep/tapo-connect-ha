> Tài liệu lịch sử local/companion đến 0.9.0. Không dùng bước đăng nhập local bên dưới để thêm entry mới. Hướng dẫn hiện hành: [README](../README.md) và [Cloud 0.10.0](../custom_components/tapo_camera_local/CLOUD_FEATURES.md).

# Tapo Connect — Camera Tapo lên Home Assistant

**Bản 0.9.0 · Đăng nhập Tapo ngay trong HA · Không cần JSON · Local + thông báo cloud**

Custom integration điều khiển camera Tapo qua mạng LAN, phát triển với mục tiêu Tapo C260. Tên thực thể, công tắc, thanh chỉnh, lựa chọn và form đã có bản dịch tiếng Việt. Có thể đăng nhập trực tiếp bằng **pytapo native** mà không cần cài “Tapo: Cameras Control” trước.

> **Đã xác minh ngày 13/09/2026:** đọc được **tên người + thời gian thông báo nhận diện thật**, qua cloud sau MFA. Smoke test HTTP thật → HA Core 2026.9.0 cô lập đã tạo 3 sensor chung và 1 sensor thời điểm theo người, đọc lại thành công. Đây **không phải HA đang dùng của chủ camera**; dependency FFmpeg được mock, không kiểm thử video. Local vẫn đọc được catalog nhưng tracking/ảnh bị từ chối. Chưa có ảnh face/Face ID từ mẫu thông báo, chưa xác minh độ ổn định nhiều ngày hoặc push realtime.

**Khách chỉ cần:** chọn **Đăng nhập Tapo cloud (tên người và thời gian)** → nhập email/mật khẩu Tapo → nhập OTP nếu được hỏi → chọn C260. **HA tự lưu phiên, không chép JSON/token, không cài mồi Tapo Control.** Xem [hướng dẫn đăng nhập](custom_components/tapo_camera_local/CLOUD_LOGIN.md). Giữ nguyên entry local/video đang hoạt động.

## Nội dung

- [Tính năng](#tính-năng)
- [Yêu cầu và tài khoản](#yêu-cầu-và-tài-khoản)
- [Cài đặt](#cài-đặt)
- [Nâng cấp và chuyển kết nối](#nâng-cấp-và-chuyển-kết-nối)
- [Danh sách thực thể](#danh-sách-thực-thể)
- [Đồng bộ và tốc độ](#đồng-bộ-và-tốc-độ)
- [Khuôn mặt](#khuôn-mặt)
- [Video RTSP](#video-rtsp)
- [Ví dụ dashboard và automation](#ví-dụ-dashboard-và-automation)
- [Xử lý lỗi](#xử-lý-lỗi)
- [Bảo mật](#bảo-mật)
- [Phát triển và GitHub](#phát-triển-và-github)

## Tính năng

- Đăng nhập tài khoản Tapo cloud ngay trong HA (email/mật khẩu + mã email nếu Tapo yêu cầu), HA tự lưu phiên.
- Sửa được chu kỳ đọc thông báo, ký lại phiên bằng **Cấu hình** / **Đăng nhập lại**.
- Từ 0.9.0 **bỏ form đăng nhập local độc lập** khi thêm integration. Entry local/companion đã tạo trước đây vẫn chạy và vẫn cấu hình được.
- Chuyển cấu hình camera thành đúng loại thực thể: **switch** cho bật/tắt, **number** cho giá trị số, **select** cho chế độ, **button** cho lệnh một lần, **text** cho lịch ghi hình nâng cao.
- Chỉ tạo control khi camera trả về trường dữ liệu có schema và giá trị hợp lệ. Không bật tính năng chỉ để dò xem nó có hoạt động không.
- Giữ sensor thông tin camera, Wi-Fi, thẻ nhớ, cảnh báo và thông tin khuôn mặt nếu có dữ liệu.
- Entry cloud độc lập đọc tên người/thời điểm từ thông báo thật; tự thêm sensor thời điểm theo từng tên, event automation riêng và bản dịch Việt/Anh.
- Đọc trước/ghi/đọc lại để xác nhận thay đổi; cập nhật HA sau lệnh, không hiển thị thành công giả.
- Poll nhanh theo cấu hình, gộp truy vấn và dùng lại kết nối/phiên đăng nhập.
- Hai entity video tùy chọn cho RTSP chất lượng cao và tiết kiệm băng thông.
- Icon riêng trong `brand/`, bản SVG gốc, diagnostics đã lược bỏ dữ liệu riêng tư, HACS custom repository.

### Chưa bao gồm

Push realtime qua ONVIF/MQTT/WebSocket, cảm biến *đang có chuyển động/người* theo event trực tiếp, đàm thoại hai chiều, gọi điện, xem/tải kho bản ghi SD/Tapo Care, cloud/P2P streaming, quản lý/xóa/đặt tên face, vẽ vùng phát hiện/riêng tư và tạo/xóa PTZ preset. Không có nút format SD, factory reset, đổi mật khẩu hoặc flash firmware. Các việc này vẫn thực hiện trong ứng dụng Tapo.

## Yêu cầu và tài khoản

- Home Assistant **2026.9.0 trở lên** là mốc hỗ trợ của gói này; bản thấp hơn chưa được kiểm thử. HA OS/Container có đầy đủ phụ thuộc là lựa chọn thuận tiện cho video.
- HA truy cập được camera qua LAN/VLAN có định tuyến và ACL phù hợp. Ví dụ camera của bạn: `192.168.1.100`, cổng điều khiển mặc định `443`.
- Camera đã được thiết lập ban đầu bằng ứng dụng Tapo. “Không cần cài mồi” nghĩa là không cần integration **Tapo Control**, không phải bỏ bước ghép camera vào Wi-Fi/Tapo ban đầu.
- HA cài dependency `pytapo==3.4.19`; integration không còn backend python-kasa cũ. `pytapo` có thể vẫn kéo `python-kasa` như dependency phụ của chính nó; integration này **không chọn** backend đó.

| Chọn trên form | Username API | Mật khẩu |
|---|---|---|
| Tài khoản Tapo / TP-Link | Luôn dùng `admin`, không dùng email | Mật khẩu tài khoản đăng nhập ứng dụng Tapo, nếu firmware chấp nhận |
| Tài khoản camera | Username tài khoản camera đã tạo trong ứng dụng | Mật khẩu Camera Account, nếu firmware chấp nhận cho API điều khiển |
| RTSP | Tài khoản camera riêng | Mật khẩu Camera Account trong URL RTSP, **không tự dùng mật khẩu Tapo** |

Chỉ thử tài khoản bạn biết chính xác, không lặp mật khẩu sai. **Local** chỉ gửi xác thực tới camera LAN. **Cloud** có form email/mật khẩu Tapo và OTP ngay trong HA, cần Internet tới TP-Link nhưng không cần camera LAN. Tài khoản Tapo không phải tài khoản đăng nhập HA hoặc Camera Account. Mật khẩu/OTP không được lưu; token được HA quản lý trong kho riêng.

## Cài đặt

### Cách 1 — ZIP thủ công

1. Sao lưu cấu hình Home Assistant và thư mục integration cũ.
2. Giải nén **`tapo_camera_local_0.9.0.zip`** vào thư mục `<HA_CONFIG>/custom_components/`.
3. Đường dẫn cuối phải là `<HA_CONFIG>/custom_components/tapo_camera_local/manifest.json`, **không lồng hai thư mục `tapo_camera_local`**. Manifest phải có version `0.9.0`.
4. Khởi động lại Home Assistant.
5. **Cài đặt → Thiết bị & dịch vụ → Thêm tích hợp → Tapo Connect**.
6. Nhập **email/mật khẩu Tapo** (đúng tài khoản dùng trong ứng dụng Tapo), mã quốc gia nếu muốn (ví dụ `VN`), nhập mã 6 chữ số qua email nếu Tapo hỏi MFA, rồi chọn C260.
7. Mở thiết bị để xem thực thể. Chỉ những chức năng đọc được mới xuất hiện; nút nguy hiểm hơn và lịch nâng cao mặc định bị tắt.

Không thay hoặc xóa `custom_components/tapo_control` khi bạn vẫn dùng nó cho camera khác.

Nếu cần thông báo face, chọn **Đăng nhập Tapo cloud** thay vì bước 6. Nhập email/mật khẩu, OTP nếu Tapo yêu cầu, chọn camera rồi hoàn tất. Không có bước chép file hoặc cấu hình token. Xem `CLOUD_LOGIN.md` trong thư mục component.

### Cách 2 — HACS custom repository

Sau khi source này được đăng GitHub:

1. **HACS → menu ba chấm → Custom repositories**.
2. Nhập URL repository chứa source này, chọn loại **Integration**.
3. Tải **Tapo Connect**, khởi động lại HA và cấu hình như trên.

Gói này chưa được công bố trong danh mục HACS chính thức. Tài liệu không giả định một URL GitHub cá nhân chưa được tạo; xem [hướng dẫn đăng GitHub](docs/GITHUB.md).

### Hiển thị tiếng Việt và icon

Đặt ngôn ngữ Home Assistant sang **Tiếng Việt** trong cấu hình ngôn ngữ/hồ sơ rồi tải lại integration/frontend. Tên đã tự đổi trong entity registry không bị ghi đè. Entity ID vẫn ổn định và không bắt buộc chứa tiếng Việt. Trạng thái máy như `on`, `off`, `available` giữ nguyên để automation hoạt động; frontend hiển thị bản dịch tương ứng.

Icon PNG tại `custom_components/tapo_camera_local/brand/` được HA hỗ trợ branding cục bộ sử dụng. Icon gốc do dự án vẽ, không phải logo chính thức của TP-Link/Tapo hoặc Home Assistant.

## Nâng cấp và chuyển kết nối

- **Từ 0.7.0 dùng profile:** entry cũ vẫn chạy. Chọn **Cấu hình lại** trên entry cloud cũ, đăng nhập Tapo/OTP và chọn đúng camera để chuyển sang kho phiên HA, giữ sensor ID. Không tự xóa profile người dùng hoặc tạo lại entry. Sau khi xác nhận hoạt động, profile cũ không còn cần cho entry đó.
- **Từ 0.6.1:** thay integration rồi restart, giữ entry hiện tại. Thêm một entry cloud mới để có tên/thời điểm thông báo; không thay cấu hình local/RTSP bằng profile cloud.
- **Từ 0.5.0 standalone:** thay đúng thư mục integration, restart. Không cần xóa entry hay nhập lại tài khoản nếu phiên đăng nhập vẫn hợp lệ.
- **Từ SSL-AES/direct thử nghiệm:** backend cũ đã bị loại bỏ. Entry được migrate sang native pytapo, giữ entry ID/device unique ID và thông tin tài khoản; nếu không xác thực được, dùng **Cấu hình lại** để chọn đúng loại tài khoản. Không có fallback âm thầm về giao thức cũ.
- **Từ companion:** menu ba chấm của entry → **Cấu hình lại** → nhập tài khoản độc lập. Chỉ lưu sau khi probe đúng ID camera. Đợi entry tải thành công rồi mới gỡ Tapo Control nếu không còn cần.
- Sensor cấu hình bật/tắt chuyển thành switch; độ nhạy ghi được chuyển thành number/select. **Domain thực thể thay đổi**, ví dụ `binary_sensor` → `switch`, nên cần sửa automation cũ. Các entity cũ không còn được cung cấp có thể còn trong registry ở trạng thái unavailable; xóa chúng sau khi đã cập nhật automation và sao lưu.
- Companion vẫn là lựa chọn tương thích **chỉ đọc sensor/face**; controls/video tiếp tục dùng Tapo Control. Muốn các control của bản này, chuyển sang standalone để tránh hai integration cùng điều khiển một cấu hình.

## Danh sách thực thể

Đây là danh mục **có thể được tạo**, không phải lời khẳng định C260 nào cũng có đủ. Số thực thể thay đổi theo firmware, dữ liệu trả về và số face. “Phát hiện người” trong nhóm switch là **bật thuật toán**, không có nghĩa đang có người trước camera.

| Loại | Chức năng |
|---|---|
| `switch` | LED trạng thái, riêng tư, bật ghi hình theo lịch, ghi đè SD, ghi âm trong video, tắt micro, khử nhiễu micro |
| `switch` | Bật phát hiện chuyển động, người, thú cưng, phương tiện, chó sủa, mèo kêu, kính vỡ, can thiệp, trẻ khóc, vượt ranh, xâm nhập, khuôn mặt |
| `switch` | Tự động theo dõi; theo dõi thông minh người/thú cưng/phương tiện/em bé khi có trường tương ứng |
| `switch` | Xoay hình 180°, hiệu chỉnh méo hình, đèn trắng, bật vùng che đã tạo, thông báo Tapo/thông báo kèm ảnh |
| `number` | Âm lượng loa/micro 0–100; độ nhạy số 1–100 cho thuật toán hỗ trợ |
| `select` | Ngày/đêm/tự động; chống nhấp nháy tự động/50/60 Hz; độ nhạy thấp/trung bình/cao cho can thiệp và trẻ khóc |
| `select` | Chuyển tới PTZ preset đã lưu. Tên kèm ID để phân biệt vị trí trùng tên; không giả định camera vẫn ở preset đó sau khi xoay bên ngoài |
| `button` | Đồng bộ ngay, xoay trái/phải/lên/xuống một bước, dừng PTZ, quét ngang/dọc/dừng quét, hiệu chuẩn PTZ, khởi động lại, bật/tắt cảnh báo thủ công |
| `text` | Bảy lịch ghi hình riêng cho từng ngày, nếu camera trả về schema `record_plan.chn1_channel` |
| `sensor` | Mẫu camera, firmware, phần cứng, ID thiết bị, MAC, IP, kiểu kết nối, RSSI/mức sóng, thẻ nhớ, thời điểm/mã cảnh báo nếu API trả về |
| `sensor` | Trạng thái API face, số face, face ID/tên/nhãn gần nhất, thời điểm nhận diện, thời điểm gần nhất của từng face |
| `sensor` (entry cloud) | Người được Tapo báo nhận diện, thời điểm thông báo, loại người quen/lạ, lần Tapo báo nhận diện từng tên gần nhất |
| `binary_sensor` | Ống kính đang che và các trạng thái chỉ đọc còn lại; companion giữ các trạng thái cấu hình chỉ đọc |
| `image` | Ảnh từng face trong catalog, **thử nghiệm** và chỉ lấy khi mở ảnh |
| `camera` | RTSP chính và RTSP phụ nếu bạn cấu hình URL tương ứng |

Nút reboot, hiệu chuẩn và bật cảnh báo thủ công mặc định **disabled**. Chỉ bật nếu muốn sử dụng. Một số firmware trả dữ liệu đọc nhưng vẫn từ chối ghi: HA sẽ báo lỗi, giữ trạng thái thực, không ép ghi bằng API khác.

### Lịch ghi hình nâng cao

Bật entity `text` tương ứng trong trang thực thể. Giá trị là JSON, ví dụ:

```json
["0000-0700:1","0700-2300:2","2300-2400:1"]
```

- `:1`: ghi liên tục; `:2`: ghi theo sự kiện/phát hiện như schema camera.
- Thời gian là giờ địa phương của camera; kiểm tra múi giờ trong ứng dụng Tapo.
- Các khoảng phải tăng dần, không chồng nhau, trong `0000`–`2400`; tối đa 10 khoảng và 255 ký tự.
- `[]` nghĩa là ngày đó không có khoảng ghi. Công tắc **Ghi hình theo lịch** là thiết lập riêng.
- Chỉ đổi ngày đang chỉnh; không ghi đè sáu ngày còn lại. Bản này không tự tạo lịch mặc định cho bạn.

## Đồng bộ và tốc độ

**Đây là near-real-time polling, không phải push realtime.**

| Hướng | Cách đồng bộ |
|---|---|
| HA → camera | Đọc giá trị hiện tại → gửi lệnh nếu cần → đọc lại xác nhận → cập nhật trạng thái HA ngay trong lượt lệnh |
| Camera/ứng dụng Tapo → HA | Poll cấu hình mặc định mỗi 5 giây; độ trễ thực tế còn phụ thuộc thời gian camera phản hồi và tải mạng |
| Danh mục/tên face, SD, thông tin ít đổi | Cache 60 giây; tối đa chu kỳ này cộng thời gian xử lý trước khi thấy thay đổi |
| Thông báo nhận diện cloud → HA | Mặc định đọc mỗi **5 giây** (cấu hình 5–300), nới ra 30 giây sau 10 phút không có sự kiện; tối đa 150 thông báo/lượt, tiếp tục trang dở. Lượt đầu nhìn lại 7 ngày, sau đó đọc tăng dần theo mốc đã lưu (mốc này được giữ qua khởi động lại) và chồng 5 phút |
| Truy vấn không hỗ trợ | Giãn thử lại khoảng 1 giờ; lỗi bị từ chối khoảng 5 phút; lỗi mạng tạm thời khoảng 30 giây |

**Cấu hình → Đồng bộ và video** (entry local/companion cũ) cho phép đổi chu kỳ 5–300 giây. Nếu camera chậm, quá nhiều request hoặc đang dùng đồng thời nhiều ứng dụng, tăng lên 10–30 giây. Nút **Đồng bộ dữ liệu ngay** bỏ cache chậm nhưng không bỏ thời gian chờ lỗi để tránh khóa camera.

**Cấu hình → Chu kỳ đọc thông báo cloud** (entry cloud) đặt nhịp đọc thông báo nhận diện từ 5–300 giây, mặc định 5 giây; HA tự nới ra 30 giây sau 10 phút yên lặng và nút **Kiểm tra thông báo Tapo ngay** ép đọc tức thì.

Transport dùng lại phiên HTTP, token đăng nhập và event loop; không dò hàng loạt tài khoản/giao thức. Các request chỉ đọc có retry hữu hạn; **lệnh ghi không tự phát lại** khi kết quả không chắc chắn. Batching tối đa 8 truy vấn có fallback đọc riêng nếu firmware từ chối batch. Các thao tác của integration được tuần tự hóa để tránh poll ghi đè state vừa đọc lại.

Lần thêm integration có một lượt probe kiểm tra tài khoản/ID rồi một phiên vận hành riêng; không giữ mật khẩu/token trong session của integration khác. Không có benchmark độ trễ C260 thật để công bố con số đăng nhập bảo đảm.

## Khuôn mặt

Các API local được truy vết từ APK: `getFaceDetectionConfig`, `searchFacesInfo`, `doSearchFaceTrackingList`, `doFaceInfoGet`. C260 thật đọc được cấu hình và 2 hồ sơ có tên; tracking/ảnh JSON trả `-40209`, thống kê/tìm video face trả `-40214` với payload đã thử. **Bản 0.7.0 lấy tên/thời gian thông báo qua cloud, không giả vờ đã sửa tracking local.** Các mục catalog/tracking dưới đây vẫn mô tả nguồn local.

- Tên/mã lấy từ catalog `face_id`, `name`, `tag`.
- Thời điểm nhận diện lấy từ tracking `traj_start_time`; không lấy giờ poll, `create_time`, `modify_time` hay `fresh_time` để giả làm lúc camera vừa nhận diện.
- Nếu chỉ có catalog, từ bản 0.6.1 mỗi hồ sơ có sensor **Tên khuôn mặt {face_id}**, state là tên người đã lưu, thuộc tính `face_id`, `tag`, `source: face_catalog`. Không cần tracking để tên khả dụng. Tên này **không phải người vừa được nhận diện**.
- Khi đổi tên trên app, sensor cập nhật theo cache catalog 60 giây; nút **Đồng bộ dữ liệu ngay** yêu cầu đọc mới. Unique ID không đổi theo tên. Khi hồ sơ bị xóa hoặc catalog mất kết nối, sensor unavailable; hồ sơ chưa có tên ở trạng thái unknown. Sensor thời điểm vẫn unavailable nếu camera không trả tracking.
- Nếu có tracking mà không có catalog, vẫn có thể có face ID/thời gian, nhưng không tự đoán tên người.
- Lịch sử truy vấn nhìn lại 1 giờ, tối đa 500 bản ghi; có cờ `history_truncated` khi vượt giới hạn. Bộ nhớ last-seen/dedupe nằm trong RAM, reset khi reload/restart; không bảo đảm phát event exactly-once qua restart.
- Event `tapo_camera_local_face_recognized` chứa `camera_id`, `face_id`, `name`, `tag`, `recognized_at`, `source`. Không phát lại toàn bộ lịch sử trong lần tải đầu.

### Ảnh face

Entity `image` tạo theo face ID trong catalog. Chỉ đọc ảnh khi HA yêu cầu, cache trong RAM 5 phút. Không ghi ảnh vào `www/`, không gửi ảnh lên cloud và không dùng snapshot toàn cảnh giả làm ảnh mặt.

`doFaceInfoGet` là API thử nghiệm: chỉ chấp nhận payload ảnh có base64/magic hợp lệ và giới hạn 5 MiB, không tải URL do camera trả về. Nếu firmware trả embedding/dữ liệu khác thay vì ảnh, entity có thể tồn tại nhưng không có ảnh để hiển thị. “Có entity image” **không** chứng minh lấy ảnh thành công. Tên người hiện trong thuộc tính ảnh và cập nhật theo catalog; tên entity dùng face ID ổn định.

### Cloud và xác thực hai bước

Đã hoàn tất MFA hợp lệ và xác minh endpoint `getAppNotificationByPage` trả tên `personName` cùng `notification.time`. Entry **Nhận diện qua thông báo cloud** tạo sensor riêng, cập nhật 30 giây và phát event `tapo_camera_local_face_notification`. Đây là giờ thông báo, chưa phải giờ bắt đầu tracking trên camera. Không đoán Face ID hoặc dùng ảnh toàn cảnh thay mặt. Mẫu API không trả ảnh/Face ID.

Xem [CLOUD_LOGIN.md](custom_components/tapo_camera_local/CLOUD_LOGIN.md) để đăng nhập/OTP ngay trong HA, chọn camera và tạo automation. HA tự lưu access/refresh token; không lưu mật khẩu/OTP, không cần file JSON. Khi token bị từ chối, thử gia hạn một lần; nếu server không cho phép thì yêu cầu đăng nhập lại qua UI. **Gia hạn thật trên session thử bị TP-Link từ chối**, chưa cam kết đăng nhập một lần vĩnh viễn. Luồng UI/MFA đã test mô phỏng; kho HA tự quản lý đã đọc được 8 notification thật và tạo 4 sensor khớp dữ liệu.

Bản 0.8.0 sửa truy vấn lịch sử theo `asc` và mốc thấp như app, thay `desc` với mốc hiện tại có thể làm mất tên/giờ ở bản trước. Không phát automation cho toàn bộ lượt tải lịch sử đầu, kể cả khi cần nhiều trang.

## Video RTSP

Trong ứng dụng Tapo, tạo **Camera Account** và cho phép chức năng RTSP/ONVIF hoặc tương thích bên thứ ba nếu firmware yêu cầu. Integration không tự bật dịch vụ này hay thay mật khẩu.

Trong **Tùy chọn → Đồng bộ và video**, nhập URL riêng, ví dụ:

```text
rtsp://CAMERA_USER:URL_ENCODED_PASSWORD@192.168.1.100:554/stream1
rtsp://CAMERA_USER:URL_ENCODED_PASSWORD@192.168.1.100:554/stream2
```

`stream1`/`stream2` là đường RTSP Tapo thường dùng; cần kiểm tra trên firmware thực. URL phải mã hóa các ký tự đặc biệt trong username/password như `@`, `#`, `:`, `/`. Không đưa URL thật vào issue hoặc ảnh chụp màn hình.

- Bỏ qua trường URL để giữ giá trị cũ; nhập chuỗi rỗng để tắt luồng tương ứng.
- HA sử dụng pipeline `stream`; ảnh xem trước dùng FFmpeg. Chưa kiểm thử phát RTSP thật/codec của C260. Browser, codec và khả năng giải mã có thể ảnh hưởng việc phát.
- Không cam kết WebRTC native, không có talkback/P2P/cloud stream. Luồng video có buffer nên không cùng độ trễ với API điều khiển.
- Khi riêng tư đang bật, integration không cung cấp nguồn video/ảnh xem trước mới. Việc một luồng đã mở dừng ngay hay còn frame trong buffer phụ thuộc camera và pipeline HA.
- Nếu HA Core tự cài ngoài image chính thức, cần FFmpeg và các thư viện media hệ thống tương thích. Kiểm thử phần nguồn URL không thay thế kiểm thử video đầu cuối.

## Ví dụ dashboard và automation

Thay entity ID bằng ID thực của bạn trong **Công cụ nhà phát triển → Trạng thái**. Đây là ví dụ, không phải ID cố định.

```yaml
type: picture-entity
entity: camera.phong_khach_video_truc_tiep
camera_view: live
show_name: true
show_state: false
```

```yaml
type: entities
title: Camera phòng khách
entities:
  - switch.phong_khach_che_do_rieng_tu
  - switch.phong_khach_phat_hien_nguoi
  - number.phong_khach_am_luong_loa
  - select.phong_khach_che_do_ngay_dem
  - sensor.phong_khach_ten_nguoi_nhan_dien_gan_nhat
  - sensor.phong_khach_thoi_diem_nhan_dien_gan_nhat
```

Ví dụ thông báo **chỉ khi camera thực sự cung cấp event face mới**:

```yaml
alias: Thông báo camera nhận diện người quen
triggers:
  - trigger: event
    event_type: tapo_camera_local_face_recognized
conditions:
  - condition: template
    value_template: "{{ trigger.event.data.get('name') not in [none, ''] }}"
actions:
  - action: persistent_notification.create
    data:
      title: Camera nhận diện khuôn mặt
      message: >-
        {{ trigger.event.data.name }} —
        {{ trigger.event.data.recognized_at }}
mode: queued
```

Nếu có nhiều camera, thêm điều kiện `camera_id`. Face ID/tên là dữ liệu riêng tư, tránh ghi ra log/notification dùng chung nếu không cần.

## Xử lý lỗi

| Hiện tượng | Kiểm tra |
|---|---|
| `Cannot connect` | IP/cổng, route/VLAN/ACL, tính tương thích TLS/session. Thông báo này **không** chứng minh firewall sai. Nếu Tapo Control chạy được, giữ nó làm fallback hoặc chọn companion |
| Sai xác thực/tạm khóa | Loại tài khoản, mật khẩu chính xác, không dùng email làm API username khi chọn Tapo. Chờ hết thời gian khóa trước khi thử lại |
| App có tên/giờ nhưng HA chưa có | Nâng lên 0.9.0, chọn Đăng nhập Tapo cloud và làm theo `CLOUD_LOGIN.md`, chờ đồng bộ lịch sử. Sensor local `catalog_only` không tự trở thành lịch sử nhận diện |
| Không có ảnh face | Chưa có catalog hoặc API không trả ảnh hợp lệ. Đây vẫn là tính năng thử nghiệm, không suy ra rằng mật khẩu sai |
| Thiếu nút/thanh chỉnh | Camera chưa trả trường tương ứng; xem entity bị tắt và `api_status`. Không tạo nút giả cho chức năng chưa được xác nhận |
| Lệnh báo không xác nhận | Camera đã từ chối/không áp dụng hoặc mất phản hồi. Kiểm tra app và refresh, không bấm lặp hàng loạt |
| Thay đổi app lên HA chậm | Kiểm tra chu kỳ poll, cache catalog/SD 60 giây, API đang backoff hoặc camera đang tải cao |
| Video trống | Thử đúng URL trong VLC từ cùng mạng, bật Camera Account/RTSP, URL-encode password, cổng 554, riêng tư, giới hạn số stream/codec/media dependencies |
| Tên còn tiếng Anh | Đổi ngôn ngữ HA, reload; tên tự đặt trước đó không bị ghi đè. Giá trị kỹ thuật/raw code có thể giữ nguyên |

### Thu thập diagnostics

Vào entry integration → **Tải xuống chẩn đoán**. Output gồm version, mode, firmware, chu kỳ poll, trạng thái API và tình trạng catalog/tracking; không chứa IP/MAC/device ID, credentials, tên/ID/ảnh face hoặc timestamps nhận diện. Kiểm tra lại trước khi đăng công khai.

Probe read-only dành cho máy trong mạng camera:

```bash
python3 -m pip install -r poc/requirements-c260.txt
python3 poc/c260_probe.py --host 192.168.1.100 --network-only
python3 poc/c260_probe.py --host 192.168.1.100 --auth-mode tapo_account --output c260_probe.json
```

Nên dùng virtualenv. Mật khẩu nhập tại prompt ẩn, không nằm trong command line. Output probe chứa face ID/thời điểm dù tên mặc định được che: **không đăng công khai**. Probe tạo file mới quyền `600`, không ghi đè file cũ. API control và RTSP thật chỉ được xác nhận khi chạy trên thiết bị của bạn.

## Bảo mật

- Camera dùng chứng chỉ TLS tự ký; transport không xác minh chứng chỉ. Chỉ dùng trong mạng tin cậy, không port-forward API/RTSP ra Internet.
- HA lưu mật khẩu API/URL RTSP trong config entry. Bảo vệ `.storage/`, backup và tài khoản HA; trường password trên form không đồng nghĩa mã hóa backup.
- Token cloud trong kho `.storage` do HA tự tạo, file riêng; integration không tự mã hóa backup. Không lưu mật khẩu/OTP. HA Recorder/event bus/backup có thể lưu tên/thời gian thật; bảo vệ quyền xem và backup.
- Gói có `cloud_app.json` chứa CA/thông số ký **dùng chung của ứng dụng**, không phải profile/tài khoản khách. Đây là giao thức reverse engineered, không phải OAuth/API chính thức được TP-Link cấp riêng cho integration. Không đóng kèm token, email/mật khẩu hoặc APK của người dùng.
- Không bật raw debug của `pytapo`, `requests`, media/FFmpeg hoặc Tapo Control khi định chia sẻ log. URL/token/payload hoặc ảnh mặt có thể xuất hiện từ các thư viện khác.
- Integration không nhận arbitrary RPC, không có service dùng để gửi payload tùy ý. Không có thao tác phá hủy dữ liệu trong UI.
- Nhận diện người là dữ liệu nhạy cảm; chỉ sử dụng camera/tài khoản bạn sở hữu hoặc được phép quản lý và tuân thủ quyền riêng tư của người xuất hiện.

## Phát triển và GitHub

Source để push: **`tapo_camera_github_0.9.0.zip`**. Hướng dẫn metadata, HACS và release: [docs/GITHUB.md](docs/GITHUB.md). Xem [CHANGELOG.md](CHANGELOG.md). Không push toàn bộ lab; profile/session/tài khoản/APK không thuộc source. Gói gồm thông số ứng dụng chung cần cho đăng nhập, người phát hành cần xem xét quyền phân phối vật liệu giao thức.

```bash
python poc/tests/run_all.py
python scripts/package_release.py
```

Chạy bằng Python 3.14.2+ có `poc/requirements-ha-test.txt`. Các test dùng camera/face tổng hợp, không gửi lệnh tới IP camera thật. Suite bao phủ payload/range, read-back, mất phản hồi không gửi lại write, reuse login/session, batching/fallback, vòng đời entity HA, tiếng Việt, options/reauth/reconfigure và ZIP sạch. Kiểm thử runtime video thật không thuộc suite.

### Nguồn và lời cảm ơn

- [pytapo — JurajNyiri](https://github.com/JurajNyiri/pytapo): transport native và schema camera được đối chiếu với bản pin 3.4.19.
- [HomeAssistant-Tapo-Control — JurajNyiri](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control): companion tái sử dụng controller do integration đó sở hữu; người dùng đã báo nó kết nối C260 được.
- [Home Assistant developer documentation](https://developers.home-assistant.io/): entity/coordinator/config flow/branding, đối chiếu thêm source HA Core 2026.9.0.
- [TP-Link: RTSP/ONVIF trên camera Tapo](https://www.tp-link.com/en/support/faq/2680/).
- APK do người dùng cung cấp: Tapo 3.18.506; báo cáo reverse engineering nằm trong workspace APK lab, **không phát hành APK/decompile** cùng repository này.

Dự án độc lập, không liên kết chính thức với TP-Link/Tapo hoặc Home Assistant. Không tuyên bố hãng hỗ trợ các API reverse engineered.
