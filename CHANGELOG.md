# Thay đổi
## 0.11.2 — 2026-09-14

- Kiểm chứng **toàn bộ luồng license trên server đang chạy thật**: đăng nhập OTP qua HTTPS,
  cấp trial, HA client kích hoạt bằng proof Ed25519, lease ký (grace offline <= 24 giờ),
  một key một bản cài, đơn PayOS thật kèm QR, webhook giả mạo và webhook ký đúng nhưng
  chưa trả tiền đều bị từ chối và không mint key, cron đối soát, admin cấp/khoá/mở khoá/reset
  và trang quản trị doanh thu + nhật ký.
- Thêm `npm run local:db` (PostgreSQL cục bộ chỉ loopback) và `npm run verify:live`
  (`scripts/live-e2e.ts` + `scripts/live-e2e-ha.py`) để tái hiện kiểm chứng; mặc định không
  tắt chống spam, chỉ bật bằng cờ `LIVE_E2E_RESET_RATE_LIMITS=true` ở môi trường lab.
- `webhook:confirm` đã được PayOS xác nhận trên kênh thật; lệnh này đổi webhook của kênh,
  cần chạy lại khi chuyển sang domain production.
- Portal 1.0.2: `typecheck` không dùng cache incremental để tránh báo cáo lỗi cũ;
  thêm script `local:db`/`verify:live`.
- Không đổi domain, entity ID, protocol, định dạng key, database schema hay camera.

## 0.11.1 — 2026-09-14

- Đồng nhất tên Tapo Connect trên Home Assistant, HACS, website, email và tài liệu.
- Đổi tên gói phát hành/script; portal 1.0.1, thư mục website trong ZIP vẫn là
  `license_server/`. Không đổi schema DB, protocol, key, domain hoặc entity ID.
- Có hướng dẫn điền PayOS vào `.env.local` riêng của server; file thật bị loại
  khỏi Git và ZIP. Không đưa secret vào custom, không bật license khi chưa deploy.

## 0.11.0 — 2026-09-14

- Thêm license độc lập Tapo Connect: link website, nhập key, private instance key,
  Ed25519 lease, kiểm tra 15 phút; cache có chữ ký tối đa 24 giờ, không quá hạn gói.
- Giữ nguyên transport, polling, entity ID, sensor, setting và chức năng camera 0.10.0.
  Không thay tài khoản Tapo bằng tài khoản website.
- License chỉ bật khi nhà phát hành cấu hình HTTPS origin và public signing key;
  mặc định bảo toàn entry cũ. Entry đã kích hoạt vẫn được kiểm tra qua restart/reauth.
- Cổng riêng Next.js/PostgreSQL: email OTP, ba gói, PayOS tự cấp key sau xác minh,
  lịch sử, admin, chống webhook lặp và proof replay. Chưa thanh toán/deploy production.
- Có adapter cho add-on đang tồn tại; không tạo add-on/bridge thừa cho camera.

## 0.10.0 — 2026-09-13

- Mở rộng đọc thông báo đúng mã trong APK: người lạ/quen, người, vật nuôi, xe,
  chuyển động, âm thanh/khóc/sủa/meo/kính vỡ/còi khói, che camera, vùng/hàng rào.
  15 loại phổ biến có timestamp + xung thông báo 60 giây; cảnh báo thẻ/pin/nhiệt,
  chuông/bưu kiện… thêm timestamp khi có bản ghi thật. Không giả làm hiện diện.
- Giữ unique ID sensor face/người; thông báo khác không ghi đè dữ liệu face.
  Event `tapo_camera_local_notification` cho mọi loại; event face cũ giữ tương thích.
- Điều khiển cloud Thing `services-sync/passthrough` bằng cùng phiên Tapo, không
  login LAN/JSON/Tapo Control. 48 setting đọc được trên C260: 28 switch, 9 number,
  4 select, 7 Text lịch ghi Disabled; PTZ/preset theo khả năng camera.
- Setting poll độc lập 30 giây, backoff tối đa 300 giây. Write có đọc trước/sau,
  không tự gửi lại nếu mất phản hồi; camera offline không chặn notification.
- Lưu riêng lịch sử latest theo loại/người trong kho HA private, khôi phục không
  replay; nâng cấp lần đầu tải rộng loại thông báo. Cursor không xóa cờ renewal
  đang chờ và không ghi đè token mới; khóa dùng chung bảo vệ các Store cùng entry.
- Sửa luồng thêm mới thực sự luôn vào cloud cả khi có Tapo Control; local/companion
  cũ giữ tương thích. Tiếng Việt/Anh, icon theo loại, README cloud và hướng dẫn
  automation đầy đủ; tài liệu local cũ được giữ, đánh dấu lịch sử.
- Kiểm chứng: cloud thật → HA Core 2026.9.0 cô lập, 136 thông báo (128 có người,
  8 người quen), 48 setting khớp; 21 sensor, 15 binary sensor, 28 switch, 9 number,
  4 select, 10 nút và 7 Text Disabled. Đã thử đổi LED và khôi phục thành công.
  Chưa gây đủ từng loại cảnh báo/chưa write toàn bộ setting trên thiết bị thật;
  không kiểm thử video, chưa triển khai lên HA khách. Chi tiết `CLOUD_FEATURES.md`.
- Bộ kiểm tra mới: 17 test transport/parser, 14 test HA tính năng cloud; thêm kiểm
  tra generator giữ bản dịch mới. Suite face/đăng nhập/local cũ tiếp tục chạy.
- Chốt release: **299 kiểm tra / 22 suite đạt** (271 unittest + 28 PASS script),
  Ruff và compileall đạt. Bằng chứng lab: `analysis/c260_live_20260913/validation_010_packaged.log`
  và `lint_010_packaged.log`; live `cloud_features_010_ha_packaged.json`.

## 0.9.0 — 2026-09-13

- **Chỉ còn đăng nhập Tapo cloud khi thêm integration.** Bỏ form "Đăng nhập độc lập" (IP + tài khoản camera) khỏi menu thêm thiết bị; entry local/companion đã tạo trước đây vẫn chạy, vẫn Cấu hình/Đăng nhập lại bình thường, không đổi entry ID hay xóa thực thể.
- **Báo nhận diện nhanh hơn:** entry cloud mặc định đọc **mỗi 5 giây** (trước đây cố định 30 giây), chỉnh được 5–300 giây trong **Cấu hình → Chu kỳ đọc thông báo cloud**; tự nới về 30 giây sau 10 phút không có sự kiện và về nhịp nhanh ngay khi có thông báo mới hoặc còn trang dở.
- Thêm nút **Kiểm tra thông báo Tapo ngay** (Diagnostic) để ép đọc cloud tức thì khi test; giữ nguyên dedupe và cửa sổ 120 giây.
- **Mốc đọc (watermark) lưu vào file phiên của HA**: khởi động lại không tải lại cửa sổ 7 ngày; watermark chỉ tiến, không lùi. Ghi tối đa mỗi 5 phút và một lần bắt buộc khi dỡ entry; lỗi ghi không chặn việc đọc.
- **Ảnh khuôn mặt/ảnh đại diện: không hỗ trợ, có bằng chứng.** 11 thông báo cloud thật của tài khoản test có `with_image_url = 0`, `with_face_id = 0`; danh mục cloud `/v1/face/recognition/list` trả `facesInfo` rỗng dù schema APK có `imageInfo.url`/`secondaryUrl`. Local: `searchFacesInfo` có tên nhưng không có đường dẫn ảnh, `doFaceInfoGet`/`doSearchFaceTrackingList` bị từ chối `-40209`. APK tải ảnh mặt bằng kênh P2P `get_face` (`libtpcommonstream`) — chưa đảo ngược/kiểm chứng, không phải HTTP local API. Không tạo thực thể ảnh, không dùng ảnh toàn cảnh thay thế.
- Kiểm thử: **266 kiểm tra / 20 suite đạt** (238 unittest + 28 PASS script) — vòng đời cloud trong HA Core lên **34** test ( polling nhanh/thích ứng, clamp chu kỳ, form Cấu hình cloud, lưu và khôi phục watermark, lỗi ghi watermark, nút refresh), runtime notification **23** test; Ruff (`--ignore EXE001`) và `compileall` đạt.
- Smoke cloud thật → HA Core cô lập bằng phiên HA tự quản lý (0.9.0): entry loaded, **8 notification**, **1 tên người**, **4 sensor** khớp tên/thời gian/loại/last-seen, `poll_interval_seconds = 5`, đúng 1 nút refresh, **0 switch/select/number/text/camera/image**, 0 event khởi động, đọc lại và unload OK. Report `analysis/c260_live_20260913/cloud_account_090_live.json`. Chưa cài trên HA người dùng; FFmpeg version vẫn mock.

## 0.8.0 — 2026-09-13

- Khách đăng nhập Tapo bằng email/mật khẩu ngay trong HA, nhận/nhập OTP nếu cần rồi chọn C260. Không nhập token, không chép JSON, không cần Tapo Control. Hỗ trợ chọn giữa nhiều C260 trong cùng tài khoản.
- HA tự lưu phiên trong Store riêng quyền 600; không lưu mật khẩu/OTP. Reconfigure/reauth giữ đúng device/sensor ID; chuyển entry profile 0.7.0 sang HA-managed mà không xóa file riêng của người dùng.
- Thử gia hạn session một lần khi token bị từ chối, lưu trạng thái trước request và token mới trước lượt đọc tiếp. Nếu bị từ chối/không rõ kết quả thì yêu cầu đăng nhập lại trong HA; không tự thử lại sau restart một lần gia hạn chưa rõ kết quả. **Gia hạn thật với session đã thử bị server từ chối**, không cam kết đăng nhập vĩnh viễn.
- Lượt cloud thật dùng cấu hình ứng dụng đóng gói và kho HA tự quản lý đọc 8 notification, tạo 4 sensor khớp tên/thời gian/loại/người, đọc lại thành công; không mock cloud/entity. Chưa làm một lần login/OTP mới qua UI HA người dùng; luồng UI đã test bằng HTTP tổng hợp và HA Core thật.
- Sửa truy vấn `desc`/mốc hiện tại của 0.7.0 gây thiếu lịch sử. Đồng bộ `asc` với cửa sổ 7 ngày và cursor, tối đa 150 thông báo/lượt, tiếp tục backlog ở lượt sau, chồng 5 phút. Không phát lại automation trong toàn bộ bootstrap nhiều trang.
- Giữ local controls/video và profile legacy. Không thêm Add-on/daemon. Thêm `CLOUD_LOGIN.md`, bản dịch và thông báo lỗi dễ dùng.
- Gói có `cloud_app.json` là CA/vật liệu giao thức ứng dụng chung; không chứa credentials cá nhân, APK hoặc dữ liệu face thật. Không công bố giá trị ký trong báo cáo.
- Runner: **256 kiểm tra / 20 suite đạt** (`analysis/c260_live_20260913/validation_080_final5.log`): 228 unittest + 28 PASS script, gồm 25 test vòng đời cloud trong HA Core thật, 18 test tài khoản cloud, 20 test runtime notification. Ruff (bỏ rule `EXE001` của helper cũ) và `compileall` đạt.
- Gói phát hành `projects/tapo_camera/dist_0.8.0/`: `tapo_camera_local_0.8.0.zip` (45 file), `tapo_camera_github_0.8.0.zip` (119 file), `SHA256SUMS_0.8.0.txt`. Audit `analysis/c260_live_20260913/archive_audit_080.json`: ZIP hợp lệ, khớp source, **0 giá trị credentials cá nhân**, vật liệu ký chung chỉ xuất hiện trong `cloud_app.json`, quyền file 600, APK gốc và archive 0.7.0 không đổi. Ví dụ IP trong tài liệu chuyển sang `192.168.1.100` để không lộ IP mạng lab.

## 0.7.0 — 2026-09-13

- Xác minh MFA hợp lệ, đọc catalog cloud/Thing passthrough và tìm được nguồn thông báo có tên/thời gian thật: `getAppNotificationByPage`. Mẫu 7 ngày có 8 thông báo người quen kèm tên; không có Face ID/ảnh. Không sửa hoặc đánh dấu thông báo đã đọc.
- Thêm entry cloud độc lập, import profile riêng đã xác minh MFA; không cần Tapo Control hay kết nối local. Giữ control, video và entry local cũ.
- Ba sensor thông báo Việt/Anh và sensor thời điểm theo từng tên; thời gian lấy từ `notification.time`, không giả là thời điểm tracking. Người lạ không giữ tên người quen cũ. Event riêng `tapo_camera_local_face_notification`, chống lặp và không chạy automation cho lịch sử lúc khởi động.
- Cloud poll 30 giây, tối đa 150 thông báo/lượt, TLS verify, không redirect/proxy môi trường. Bảo vệ đường dẫn/UID/quyền profile; phiên hết hạn yêu cầu profile mới, không tự login/retry mật khẩu. Diagnostics chỉ có counts/status.
- Smoke test HTTP cloud thật → HA Core 2026.9.0 cô lập tạo đủ 4 sensor với mẫu hiện tại, khớp tên/thời gian/loại/người, đọc lại thành công. Mẫu nguồn có thể thay đổi; số sensor phụ thuộc người có trong lịch sử. Chỉ mock phiên bản FFmpeg, không mock cloud/entity. Chưa triển khai HA người dùng hoặc kiểm thử ảnh/video thật.
- Thêm PoC đọc cloud/Thing/notification, exporter profile, smoke test riêng, kiểm thử offline/API/HA; bổ sung hướng dẫn `CLOUD_NOTIFICATIONS.md` đầy đủ trong ZIP.
- Runner đạt **223 kiểm thử / 19 suite**, gồm 28 HA local và 12 HA notification; syntax/compile và Ruff đạt với rule quyền executable `EXE001` của helper cũ được loại khỏi lượt lint này. Không sửa helper nghiên cứu cũ chỉ để đổi file mode.
- Giữ archive 0.6.0/0.6.1; không kèm APK, profile, tài khoản, token, khóa ký hoặc dữ liệu mặt thật vào bản cài/source.

## 0.6.1 — 2026-09-13

- Thêm sensor **Tên khuôn mặt {face_id}** cho từng hồ sơ trong danh mục, không phụ thuộc API lịch sử. Tên đổi theo catalog, unique ID giữ nguyên; hồ sơ bị xóa/mất catalog trở thành unavailable, hồ sơ chưa đặt tên không tự đoán tên.
- Bổ sung bản dịch Việt/Anh và icon cho sensor tên. Không dùng tên trong catalog làm “người vừa nhận diện”, không dùng `fresh_time` làm thời điểm sự kiện.
- Xác minh C260 thật đọc được catalog có tên qua local; snapshot 11:33 UTC trả 2 hồ sơ có tên. Tracking/ảnh JSON bị từ chối `-40209`; thống kê/tìm video face bị từ chối `-40214` với payload đã thử. Snapshot toàn bộ vẫn có lỗi phiên ở các lần khác, chưa xác minh ổn định trên HA người dùng.
- Thêm PoC cloud độc lập: chữ ký và CA lấy từ APK do người dùng cung cấp; giữ xác minh TLS, dùng đúng `appServerUrlV2` theo vùng để đăng nhập. Thử thật đã tới bước MFA, chưa có token/dữ liệu camera cloud. Không tích hợp cloud chưa kiểm chứng vào HA.
- Thêm 2 kiểm thử vòng đời HA cho catalog-only và 14 kiểm thử offline cho cloud, nâng tổng runner lên 145 test cases.
- Giữ nguyên archive 0.6.0 và không đưa file tài khoản, token, APK hoặc dữ liệu mặt thật vào gói cài/source.

## 0.6.0 — 2026-09-13

- Bỏ lựa chọn SSL-AES thử nghiệm và fallback python-kasa khỏi integration. Entry cũ được chuyển sang native pytapo, giữ entry ID và unique ID thiết bị; có thể cần xác thực lại nếu tài khoản cũ không phù hợp.
- Đăng nhập độc lập hoặc companion chỉ đọc. Không sao chép tài khoản của Tapo Control.
- Bổ sung switch, number, select, button và text theo dữ liệu camera thực sự trả về. Chặn payload ghi ngoài danh sách, tham số sai và lệnh phá hủy dữ liệu.
- Đọc trước/ghi/đọc lại cấu hình; không giả lập thành công hoặc tự gửi lại lệnh ghi khi mất phản hồi. Đọc lại trạng thái HA ngay sau lệnh.
- Poll nhanh 5 giây mặc định, điều chỉnh 5–300 giây. Gộp tối đa 8 truy vấn/lần nếu camera hỗ trợ; danh mục face, thẻ nhớ và thông tin ít đổi đọc mỗi 60 giây.
- Tái sử dụng phiên HTTP, session đăng nhập và executor event loop; không chạy dò giao thức của high-level constructor.
- Việt hóa tên và các trạng thái enum; thêm bản dịch tiếng Anh. Tên tự đặt và entity ID hiện có không bị đổi hàng loạt.
- Hai entity RTSP riêng; video không sử dụng mật khẩu API làm mật khẩu RTSP.
- Sửa nguồn video theo API `Camera.stream_source()` của HA; xử lý lỗi FFmpeg mà không ghi URL chứa mật khẩu. Kiểm thử dispatch qua API camera của HA.
- Cấu hình lại và thay tùy chọn chỉ tải lại entry một lần, tránh tạo hai phiên đăng nhập; dùng `OptionsFlowWithReload`.
- Runner/CI thống nhất 118 test cases mô phỏng, gồm 26 kiểm tra vòng đời HA Core; không chạy trùng các suite.
- Icon SVG gốc và PNG trong `brand/`, tài liệu cài đặt/kiểm thử/GitHub, HACS custom repository và đóng gói sạch.
- **Chỉ kiểm thử mô phỏng/offline. Chưa kiểm thử C260 thật, luồng RTSP thật hoặc push realtime.**

## 0.5.0

- Đăng nhập standalone bằng pytapo; reauth/reconfigure; chuyển companion sang standalone.
- Giữ sensor face và ảnh face thử nghiệm. Chưa có control standalone.

## 0.4.0 / 0.3.0

- Ảnh face thử nghiệm và companion dùng controller của Tapo: Cameras Control.
