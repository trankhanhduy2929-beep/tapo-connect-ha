# Đăng repository GitHub

## Chỉ đăng source integration

Giải nén `tapo_connect_github_public_0.11.2.zip` vào một thư mục mới. Root repository phải chứa `custom_components/`, `README.md`, `hacs.json`, `.github/`; **không** thêm `license_server/`, `poc/`, `scripts/` hay thư mục lab.

Không push toàn bộ thư mục APK lab. Gói GitHub không chứa APK, decompile, ảnh khuôn mặt thật, log máy người dùng, virtualenv, cấu hình HA hay source portal license.

Không đăng `private/`, `tapo_private/`, `.storage/`, profile cloud MFA hoặc token/session/tài khoản thật. `cloud_app.json` là cấu hình giao thức **chung** đi kèm integration, không chứa tài khoản khách; có CA và vật liệu ký trích từ APK, không coi đây là khóa OAuth công khai/chính thức. Người phát hành cần xem xét quyền phân phối vật liệu giao thức.

## Điền địa chỉ repository

Trước khi push, sửa `custom_components/tapo_camera_local/manifest.json`:

```json
"documentation": "https://github.com/TEN_GITHUB/TEN_REPO",
"issue_tracker": "https://github.com/TEN_GITHUB/TEN_REPO/issues"
```

Và điền `codeowners` nếu muốn nhận credit.

## HACS và phát hành

1. Tạo repository **public** rồi push source.
2. Tạo tag/release `v0.11.2`, đính kèm `tapo_connect_0.11.2.zip` + SHA256.
3. Người dùng thêm URL repository vào **HACS → Custom repositories → Integration**.
4. Đây là custom repository, **không** mặc định trong danh mục HACS chính thức.
5. Issue template chỉ yêu cầu diagnostics đã che dữ liệu; không yêu cầu mật khẩu, token, ảnh mặt công khai.

Không cần Add-on, MQTT broker, daemon, sửa Home Assistant core hay frontend tùy chỉnh.
