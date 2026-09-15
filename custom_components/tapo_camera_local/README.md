# Tapo Connect 0.11.2 — camera giữ nguyên, license Tapo Connect độc lập

Nâng cấp này giữ nguyên tính năng camera 0.10.0. License mặc định chưa bắt buộc khi
chưa cấu hình website; nhà phát hành bật bằng script publisher sau khi deploy server.
Đọc [LICENSE_GUIDE.md](LICENSE_GUIDE.md) để đăng ký, dùng thử, nhập key hoặc chuyển máy.

Tài liệu hiện hành: **`CLOUD_FEATURES.md`** (sensor/setting/automation) và `CLOUD_LOGIN.md` (đăng nhập/OTP). `HUONG_DAN.md` là tài liệu lịch sử cho entry local cũ.

1. Đặt thư mục này tại `<HA_CONFIG>/custom_components/tapo_camera_local/`.
2. Restart Home Assistant 2026.9.0+, thêm **Tapo Connect** → nhập **email/mật khẩu Tapo** (nhập mã email nếu Tapo hỏi MFA) rồi chọn C260. Từ 0.9.0 đây là cách duy nhất để thêm mới; không cần cài Tapo Control trước.
3. Entry cloud giữ sensor tên/thời điểm theo người, thêm thông báo người lạ/người/vật nuôi/xe/âm thanh…, switch, number, select, lịch ghi và PTZ khi camera hỗ trợ. Setting đọc mỗi 30 giây; thông báo độc lập 5 giây mặc định, giãn 30 giây khi nhàn rỗi.
4. Entry local/companion cũ vẫn chạy. Entry cloud mới điều khiển setting trực tiếp qua cloud, không cần Tapo Control. Video cloud và ảnh face chưa triển khai; không thay thế luồng local đang có.

**Tên + thời gian như thông báo trên app:** chọn **Đăng nhập Tapo cloud (tên người và thời gian)**, nhập email/mật khẩu Tapo, OTP nếu cần rồi chọn C260. **HA tự lưu phiên, không cần file JSON hoặc cài mồi Tapo Control.** Xem `CLOUD_LOGIN.md`. Giữ local/control/video đang hoạt động; entry profile cũ có thể chuyển qua Cấu hình lại.

Đã kiểm thử ngày 13/09/2026: cloud thật → HA Core cô lập, 136 thông báo (người/người quen), 48 setting khớp trạng thái, 7 lịch ghi đăng ký nhưng Disabled. Đã đổi LED rồi khôi phục và đọc xác nhận. Thời điểm là thông báo, không giả là tracking local; poll thông báo 5/30 giây, setting 30 giây. Chưa cài lên HA của người dùng, chưa thử đủ loại cảnh báo/setting, RTSP hoặc chạy nhiều ngày.

Luồng login/OTP và HA tự quản lý phiên được test mô phỏng; session thật đã đọc thông báo thành công qua kho HA. Gia hạn session thật bị server từ chối, nên không cam kết đăng nhập một lần vĩnh viễn; HA yêu cầu đăng nhập lại qua UI khi cần. Không lưu mật khẩu/OTP; bảo vệ kho phiên và backup của HA.

Local giữ catalog có tên và các control hiện có, không còn backend SSL-AES thử nghiệm cũ. Đồng bộ local bằng đọc lại sau lệnh và polling 5 giây; tracking/ảnh C260 vẫn bị từ chối. Xem hướng dẫn trước khi bật reboot, hiệu chuẩn, cảnh báo hoặc sửa lịch ghi hình.
