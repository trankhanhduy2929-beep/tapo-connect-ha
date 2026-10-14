// Tapo Connect management panel. Plain web component, no build step.
// Styling uses Home Assistant theme tokens only; flat by default.

const TAG_LABELS = {
  familiar: "Người quen",
  stranger: "Người lạ",
  person: "Có người",
  pet: "Thú cưng",
  vehicle: "Xe",
  motion: "Chuyển động",
  audio: "Âm thanh",
  baby_cry: "Tiếng trẻ khóc",
  bark: "Tiếng chó sủa",
  meow: "Tiếng mèo kêu",
  glass_break: "Vỡ kính",
  smoke_alarm: "Báo khói",
  tampering: "Che camera",
  intrusion: "Xâm nhập",
  line_crossing: "Vượt vạch",
  package_delivered: "Giao hàng",
  package_removed: "Lấy hàng",
  doorbell: "Chuông cửa",
  missed_doorbell: "Chuông nhỡ",
  loitering: "Lang thang",
  anti_theft: "Chống trộm",
  multiple_detection: "Phát hiện hỗn hợp",
  person_enhanced: "Người",
};

const CATEGORY_LABELS = {
  config: "Cấu hình",
  diagnostic: "Chẩn đoán",
};

const HISTORY_TAGS = [
  "familiar", "stranger", "person", "motion", "pet", "vehicle", "audio",
  "baby_cry", "bark", "meow", "glass_break", "smoke_alarm", "tampering",
  "intrusion", "line_crossing", "package_delivered", "package_removed",
  "doorbell", "loitering", "anti_theft",
];

const TABS = [
  { id: "settings", label: "Cài đặt" },
  { id: "faces", label: "Face ID" },
  { id: "history", label: "Lịch sử" },
];

const css = `
  :host {
    display: block;
    background: var(--primary-background-color, #f5f5f5);
    color: var(--primary-text-color, #212121);
    min-height: 100vh;
    box-sizing: border-box;
  }
  * { box-sizing: border-box; }
  .wrap { max-width: 1080px; margin: 0 auto; padding: 16px; }
  header.top { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between; margin-bottom: 16px; }
  h1 { font-size: 1.35rem; margin: 0; font-weight: 600; }
  .picker { display: flex; align-items: center; gap: 8px; }
  select, input[type="text"], input[type="search"], input[type="number"] {
    font: inherit;
    color: var(--primary-text-color, #212121);
    background: var(--card-background-color, #fff);
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: 8px;
    padding: 8px 10px;
    min-height: 40px;
    width: 100%;
  }
  select { min-width: 220px; }
  .card {
    background: var(--card-background-color, #fff);
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: var(--ha-card-border-radius, 12px);
    margin-bottom: 16px;
  }
  .card > h2 {
    font-size: 0.95rem;
    font-weight: 600;
    margin: 0;
    padding: 12px 16px;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
    color: var(--secondary-text-color, #727272);
    text-transform: none;
  }
  .card .body { padding: 4px 16px 12px; }
  .row {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 12px;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
  }
  .card .body > .row:last-child { border-bottom: 0; }
  .row .label { min-width: 0; }
  .row .label .name { overflow-wrap: anywhere; }
  .row .label .hint { font-size: 0.8rem; color: var(--secondary-text-color, #727272); margin-top: 2px; }
  .row[data-unavailable="true"] { opacity: 0.55; }
  .row .control { justify-self: end; display: flex; align-items: center; gap: 8px; }
  .row .control.wide { width: 100%; }
  .switch {
    width: 52px; height: 32px; border-radius: 16px; border: 1px solid var(--divider-color, #e0e0e0);
    background: var(--secondary-background-color, #e5e5e5); position: relative; cursor: pointer; padding: 0;
  }
  .switch::after {
    content: ""; position: absolute; top: 3px; left: 3px; width: 24px; height: 24px; border-radius: 50%;
    background: var(--card-background-color, #fff); border: 1px solid var(--divider-color, #e0e0e0);
    transition: transform 120ms ease;
  }
  .switch[aria-checked="true"] { background: var(--primary-color, #03a9f4); border-color: var(--primary-color, #03a9f4); }
  .switch[aria-checked="true"]::after { transform: translateX(20px); }
  .switch:disabled { cursor: default; }
  .range { display: flex; align-items: center; gap: 10px; width: 260px; max-width: 60vw; }
  .range input[type="range"] { width: 100%; accent-color: var(--primary-color, #03a9f4); }
  .range output { font-variant-numeric: tabular-nums; min-width: 3.5ch; text-align: right; }
  .btn {
    font: inherit; cursor: pointer; min-height: 40px; padding: 8px 14px;
    border-radius: 8px; border: 1px solid var(--divider-color, #e0e0e0);
    background: var(--card-background-color, #fff); color: var(--primary-text-color, #212121);
  }
  .btn:hover { background: var(--secondary-background-color, rgba(0,0,0,0.05)); }
  .btn.primary { background: var(--primary-color, #03a9f4); border-color: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); }
  .btn:disabled { opacity: 0.5; cursor: default; }
  :is(.btn, select, input, .switch):focus-visible { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: 2px; }
  .tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--divider-color, #e0e0e0); margin-bottom: 16px; overflow-x: auto; }
  .tabs button {
    font: inherit; cursor: pointer; background: none; border: 0; padding: 10px 14px; color: var(--secondary-text-color, #727272);
    border-bottom: 2px solid transparent; white-space: nowrap;
  }
  .tabs button[aria-selected="true"] { color: var(--primary-color, #03a9f4); border-bottom-color: var(--primary-color, #03a9f4); font-weight: 600; }
  .banner {
    display: flex; gap: 10px; padding: 10px 14px; border-radius: 8px; margin-bottom: 16px;
    border: 1px solid var(--divider-color, #e0e0e0); background: var(--card-background-color, #fff); align-items: flex-start;
  }
  .banner.warn { border-color: var(--warning-color, #ff9800); }
  .banner.error { border-color: var(--error-color, #f44336); }
  .banner .txt { min-width: 0; }
  .banner .title { font-weight: 600; margin-bottom: 2px; }
  .muted { color: var(--secondary-text-color, #727272); }
  .empty { padding: 28px 16px; text-align: center; color: var(--secondary-text-color, #727272); }
  .list .item { display: flex; gap: 12px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--divider-color, #e0e0e0); }
  .card .body > .item:last-child { border-bottom: 0; }
  .avatar {
    width: 44px; height: 44px; border-radius: 50%; flex: none; display: grid; place-items: center;
    background: var(--secondary-background-color, #e5e5e5); color: var(--secondary-text-color, #727272);
    font-weight: 600; overflow: hidden; border: 1px solid var(--divider-color, #e0e0e0);
  }
  .avatar img { width: 100%; height: 100%; object-fit: cover; }
  .item .grow { min-width: 0; flex: 1; }
  .item .name { font-weight: 600; overflow-wrap: anywhere; }
  .item .meta { font-size: 0.82rem; color: var(--secondary-text-color, #727272); margin-top: 2px; }
  .badge {
    display: inline-block; font-size: 0.75rem; padding: 2px 8px; border-radius: 999px;
    border: 1px solid var(--divider-color, #e0e0e0); color: var(--secondary-text-color, #727272);
    background: var(--secondary-background-color, rgba(0,0,0,0.04)); white-space: nowrap;
  }
  .badge.familiar { border-color: var(--success-color, #4caf50); color: var(--success-color, #4caf50); }
  .badge.stranger { border-color: var(--warning-color, #ff9800); color: var(--warning-color, #ff9800); }
  .toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
  .toolbar select { min-width: 180px; }
  .spacer { flex: 1; }
  .list .item { flex-wrap: wrap; }
  .face-actions { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; justify-content: flex-end; }
  .face-actions select { min-width: 130px; width: auto; }
  .btn.small { min-height: 32px; padding: 4px 10px; font-size: 0.85rem; }
  .btn.danger { border-color: var(--error-color, #f44336); color: var(--error-color, #f44336); }
  .form-card .field { display: grid; gap: 6px; margin: 12px 0; }
  .form-card .field label { font-size: 0.85rem; color: var(--secondary-text-color, #727272); }
  .form-card .actions { display: flex; gap: 8px; margin-top: 4px; }
  .form-card input[type="file"] { width: 100%; min-height: 40px; }
  .statusline { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; margin-bottom: 16px; font-size: 0.85rem; color: var(--secondary-text-color, #727272); }
  .dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; margin-right: 6px; background: var(--secondary-text-color, #727272); vertical-align: middle; }
  .dot.on { background: var(--success-color, #4caf50); }
  .dot.off { background: var(--error-color, #f44336); }
  .toast {
    position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%);
    background: var(--card-background-color, #fff); color: var(--primary-text-color, #212121);
    border: 1px solid var(--divider-color, #e0e0e0); border-radius: 8px; padding: 10px 16px;
    z-index: 10; max-width: 90vw;
  }
  .toast.error { border-color: var(--error-color, #f44336); }
  .loading { padding: 28px; text-align: center; color: var(--secondary-text-color, #727272); }
  @media (max-width: 560px) {
    .row { grid-template-columns: 1fr; }
    .row .control { justify-self: stretch; }
    .range { width: 100%; max-width: none; }
    header.top { flex-direction: column; align-items: stretch; }
    select { min-width: 0; }
  }
  @media (prefers-reduced-motion: reduce) {
    * { transition: none !important; }
  }
`;

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const tagLabel = (tag) => TAG_LABELS[tag] || tag || "";

const formatTime = (iso) => {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("vi-VN");
};

class TapoConnectPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._loaded = false;
    this._tab = "settings";
    this._cameras = [];
    this._entryId = null;
    this._overview = null;
    this._faces = null;
    this._history = null;
    this._tag = "";
    this._busy = false;
    this._error = null;
    this._toast = null;
    this._toastTimer = null;
    this._faceAddOpen = false;
    this._editingFace = null;
    this._confirmDelete = null;
    this._onChange = this._onChange.bind(this);
    this._onClick = this._onClick.bind(this);
  }

  set hass(value) {
    this._hass = value;
    if (!this._loaded && value) {
      this._loaded = true;
      this._bootstrap();
    }
  }

  get hass() {
    return this._hass;
  }

  set narrow(value) {
    this._narrow = value;
  }

  disconnectedCallback() {
    if (this._toastTimer) clearTimeout(this._toastTimer);
  }

  async _call(type, payload = {}) {
    return this._hass.callWS({ type, ...payload });
  }

  async _bootstrap() {
    this._render();
    try {
      const result = await this._call("tapo_camera_local/cameras");
      this._cameras = result.cameras || [];
      if (this._cameras.length && !this._entryId) {
        this._entryId = this._cameras[0].entry_id;
      }
    } catch (err) {
      this._error = "Không tải được danh sách camera.";
    }
    await this._loadTab();
    this._render();
  }

  _camera() {
    return this._cameras.find((item) => item.entry_id === this._entryId) || null;
  }

  async _loadTab() {
    this._error = null;
    if (!this._entryId) {
      this._render();
      return;
    }
    this._render();
    try {
      if (this._tab === "settings") {
        this._overview = await this._call("tapo_camera_local/overview", { entry_id: this._entryId });
      } else if (this._tab === "faces") {
        this._faces = await this._call("tapo_camera_local/faces", { entry_id: this._entryId });
      } else {
        this._history = await this._call("tapo_camera_local/history", {
          entry_id: this._entryId,
          tag: this._tag || null,
          limit: 100,
        });
      }
    } catch (err) {
      this._error = "Không đọc được dữ liệu. Thử lại sau.";
    }
    this._render();
  }

  _showToast(message, isError = false) {
    this._toast = { message, isError };
    if (this._toastTimer) clearTimeout(this._toastTimer);
    this._render();
    this._toastTimer = setTimeout(() => {
      this._toast = null;
      this._render();
    }, 3200);
  }

  async _onChange(event) {
    const target = event.target;
    if (!target || !target.dataset) return;
    if (target.dataset.role === "face-tag") {
      await this._submitFaceTag(target.dataset.faceId, target.value);
      return;
    }
    if (!target.dataset.entity) return;
    if (target.dataset.role === "tag") {
      this._tag = target.value;
      await this._loadTab();
      return;
    }
    if (target.dataset.role === "camera") {
      this._entryId = target.value;
      this._overview = null;
      this._faces = null;
      this._history = null;
      await this._loadTab();
      return;
    }
    if (target.dataset.role === "switch") return;

    const entityId = target.dataset.entity;
    const domain = target.dataset.domain;
    const service = target.dataset.service;
    let data = { entity_id: entityId };
    if (domain === "number") data.value = Number(target.value);
    else if (domain === "select") data.option = target.value;
    else if (domain === "text") {
      if (target.value === target.dataset.original) return;
      data.value = target.value;
    }
    await this._callService(domain, service, data, entityId);
  }

  async _onClick(event) {
    const target = event.target.closest("[data-action], [data-entity]");
    if (!target) return;
    const action = target.dataset.action;
    if (action === "tab") {
      this._tab = target.dataset.tab;
      await this._loadTab();
      return;
    }
    if (action === "refresh") {
      await this._loadTab();
      return;
    }
    if (action && action.startsWith("face-")) {
      await this._onFaceAction(action, target);
      return;
    }
    if (target.dataset.role === "switch" && target.dataset.entity) {
      const next = target.getAttribute("aria-checked") !== "true";
      target.setAttribute("aria-checked", String(next));
      await this._callService("switch", next ? "turn_on" : "turn_off", { entity_id: target.dataset.entity }, target.dataset.entity);
      return;
    }
    if (target.dataset.role === "press" && target.dataset.entity) {
      await this._callService("button", "press", { entity_id: target.dataset.entity }, target.dataset.entity);
    }
  }

  async _callService(domain, service, data, entityId) {
    if (!this._hass || this._busy) return;
    this._busy = true;
    try {
      await this._hass.callService(domain, service, data);
      this._showToast("Đã gửi lệnh.");
      if (this._tab === "settings") {
        await new Promise((resolve) => setTimeout(resolve, 400));
        this._overview = await this._call("tapo_camera_local/overview", { entry_id: this._entryId });
      }
    } catch (err) {
      this._showToast("Không thực hiện được lệnh.", true);
      if (this._tab === "settings") {
        try {
          this._overview = await this._call("tapo_camera_local/overview", { entry_id: this._entryId });
        } catch (ignored) {
          /* keep previous view */
        }
      }
    } finally {
      this._busy = false;
      this._render();
    }
    void entityId;
  }

  async _onFaceAction(action, target) {
    const faceId = target.dataset.faceId;
    if (action === "face-add-open") {
      this._faceAddOpen = true;
      this._render();
      return;
    }
    if (action === "face-add-cancel") {
      this._faceAddOpen = false;
      this._render();
      return;
    }
    if (action === "face-add-submit") {
      await this._submitFaceAdd();
      return;
    }
    if (action === "face-add-snapshot") {
      await this._submitFaceAdd(true);
      return;
    }
    if (action === "face-edit") {
      this._editingFace = faceId;
      this._confirmDelete = null;
      this._render();
      return;
    }
    if (action === "face-edit-cancel") {
      this._editingFace = null;
      this._render();
      return;
    }
    if (action === "face-edit-save") {
      const input = this.shadowRoot.querySelector('[data-role="face-rename"]');
      await this._submitFaceRename(faceId, input ? input.value : "");
      return;
    }
    if (action === "face-delete") {
      this._confirmDelete = faceId;
      this._editingFace = null;
      this._render();
      return;
    }
    if (action === "face-delete-cancel") {
      this._confirmDelete = null;
      this._render();
      return;
    }
    if (action === "face-delete-confirm") {
      await this._faceCommand("tapo_camera_local/face_delete", { entry_id: this._entryId, face_id: faceId }, "Đã xoá khuôn mặt.");
    }
  }

  _readFaceImage() {
    const input = this.shadowRoot.querySelector('[data-role="face-image"]');
    const file = input && input.files && input.files[0];
    if (!file) return Promise.reject(new Error("Hãy chọn ảnh chân dung."));
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error("Không đọc được ảnh."));
      reader.readAsDataURL(file);
    });
  }

  async _submitFaceAdd(useSnapshot = false) {
    const name = (this.shadowRoot.querySelector('[data-role="face-name"]') || {}).value || "";
    const tag = (this.shadowRoot.querySelector('[data-role="face-tag-new"]') || {}).value || "familiar";
    const payload = { entry_id: this._entryId, name: name.trim(), tag };
    if (useSnapshot) {
      payload.use_snapshot = true;
    } else {
      try {
        payload.image = await this._readFaceImage();
      } catch (err) {
        this._showToast(err.message, true);
        return;
      }
    }
    await this._faceCommand("tapo_camera_local/face_add", payload, "Đã thêm khuôn mặt.");
  }

  async _submitFaceRename(faceId, name) {
    await this._faceCommand("tapo_camera_local/face_update", { entry_id: this._entryId, face_id: faceId, name: name.trim() }, "Đã đổi tên.");
  }

  async _submitFaceTag(faceId, tag) {
    await this._faceCommand("tapo_camera_local/face_update", { entry_id: this._entryId, face_id: faceId, tag }, "Đã đổi nhóm.");
  }

  async _faceCommand(type, payload, message) {
    if (!this._hass || this._busy) return;
    this._busy = true;
    this._render();
    try {
      await this._call(type, payload);
      this._showToast(message);
      this._faceAddOpen = false;
      this._editingFace = null;
      this._confirmDelete = null;
      this._faces = await this._call("tapo_camera_local/faces", { entry_id: this._entryId });
    } catch (err) {
      this._showToast(err && err.message ? err.message : "Không thực hiện được lệnh.", true);
    } finally {
      this._busy = false;
      this._render();
    }
  }

  _renderHeader() {
    const camera = this._camera();
    const options = this._cameras
      .map((item) => `<option value="${esc(item.entry_id)}"${item.entry_id === this._entryId ? " selected" : ""}>${esc(item.name)}</option>`)
      .join("");
    const picker = this._cameras.length
      ? `<div class="picker"><label class="muted" for="cam">Camera</label><select id="cam" data-role="camera" aria-label="Chọn camera">${options}</select></div>`
      : "";
    const status = camera
      ? `<div class="statusline">
           <span><span class="dot ${camera.available ? "on" : "off"}"></span>${camera.available ? "Trực tuyến" : "Ngoại tuyến"}</span>
           <span class="muted">${esc(camera.model || "")}</span>
           <span class="muted">${camera.mode === "cloud" ? "Cloud thông báo" : "Kết nối nội bộ"}</span>
         </div>`
      : "";
    return `<header class="top"><h1>Tapo Connect</h1>${picker}</header>${status}`;
  }

  _renderTabs() {
    return `<div class="tabs" role="tablist">${TABS.map(
      (tab) =>
        `<button type="button" role="tab" data-action="tab" data-tab="${tab.id}" aria-selected="${this._tab === tab.id}">${tab.label}</button>`
    ).join("")}</div>`;
  }

  _renderBanner() {
    if (this._error) {
      return `<div class="banner error" role="alert"><div class="txt"><div class="title">Không đọc được dữ liệu</div><div class="muted">${esc(this._error)}</div></div></div>`;
    }
    return "";
  }

  _renderControl(item) {
    const disabled = item.available ? "" : " disabled";
    if (item.domain === "switch") {
      const on = item.value === "on";
      return `<button type="button" class="switch" role="switch" data-role="switch" data-entity="${esc(item.entity_id)}" aria-checked="${on}" aria-label="${esc(item.name)}"${disabled}></button>`;
    }
    if (item.domain === "number") {
      const min = item.min ?? 0;
      const max = item.max ?? 100;
      const step = item.step ?? 1;
      const value = item.value ?? min;
      return `<div class="range"><input type="range" data-entity="${esc(item.entity_id)}" data-domain="number" data-service="${esc(item.service)}" min="${min}" max="${max}" step="${step}" value="${esc(value)}" aria-label="${esc(item.name)}"${disabled}><output>${esc(value)}${item.unit ? " " + esc(item.unit) : ""}</output></div>`;
    }
    if (item.domain === "select") {
      const options = (item.options || [])
        .map((option) => `<option value="${esc(option)}"${option === item.value ? " selected" : ""}>${esc(option)}</option>`)
        .join("");
      return `<select data-entity="${esc(item.entity_id)}" data-domain="select" data-service="${esc(item.service)}" aria-label="${esc(item.name)}"${disabled}>${options}</select>`;
    }
    if (item.domain === "text") {
      return `<input type="text" data-entity="${esc(item.entity_id)}" data-domain="text" data-service="${esc(item.service)}" data-original="${esc(item.value)}" value="${esc(item.value)}" aria-label="${esc(item.name)}"${disabled}>`;
    }
    return `<button type="button" class="btn" data-role="press" data-entity="${esc(item.entity_id)}"${disabled}>Chạy</button>`;
  }

  _renderSettings() {
    const data = this._overview;
    if (!data) return `<div class="loading">Đang tải…</div>`;
    const controls = data.settings || [];
    if (!controls.length) {
      return `<div class="empty">Camera này chưa có điều khiển nào khả dụng.</div>`;
    }
    const groups = new Map();
    for (const item of controls) {
      const key = item.category || "control";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(item);
    }
    const order = ["control", "config", "diagnostic"];
    const cards = [];
    for (const key of [...groups.keys()].sort((a, b) => order.indexOf(a) - order.indexOf(b))) {
      const items = groups.get(key);
      const title = key === "control" ? "Điều khiển" : CATEGORY_LABELS[key] || key;
      const rows = items
        .map(
          (item) => `<div class="row" data-unavailable="${!item.available}">
            <div class="label"><div class="name">${esc(item.name)}</div></div>
            <div class="control">${this._renderControl(item)}</div>
          </div>`
        )
        .join("");
      cards.push(`<section class="card"><h2>${esc(title)}</h2><div class="body">${rows}</div></section>`);
    }
    const observations = data.observations || [];
    if (observations.length) {
      const rows = observations
        .map(
          (item) => `<div class="row"><div class="label"><div class="name">${esc(item.name)}</div></div>
            <div class="control"><span class="badge">${esc(item.value)}${item.unit ? " " + esc(item.unit) : ""}</span></div></div>`
        )
        .join("");
      cards.push(`<section class="card"><h2>Trạng thái</h2><div class="body">${rows}</div></section>`);
    }
    const license = data.license || {};
    cards.push(this._renderLicense(license));
    return cards.join("");
  }

  _renderLicense(license) {
    let text = "Chưa kích hoạt bản quyền.";
    let badge = "Chưa kích hoạt";
    if (license.activated && license.status === "active") {
      badge = "Đang hoạt động";
      text = license.valid_until ? `Hạn dùng đến ${formatTime(license.valid_until)}` : "Đang hoạt động.";
    } else if (license.status === "trial") {
      badge = "Bản dùng thử";
      text = license.valid_until ? `Dùng thử đến ${formatTime(license.valid_until)}` : "Bản dùng thử.";
    } else if (license.status === "expired") {
      badge = "Hết hạn";
    } else if (license.activated) {
      badge = license.status || "Đã kích hoạt";
    }
    return `<section class="card"><h2>Bản quyền</h2><div class="body"><div class="row">
      <div class="label"><div class="name">License</div><div class="hint">${esc(text)}</div></div>
      <div class="control"><span class="badge">${esc(badge)}</span></div>
    </div></div></section>`;
  }

  _renderFaces() {
    const data = this._faces;
    if (!data) return `<div class="loading">Đang tải…</div>`;
    if (data.mode === "cloud") {
      const people = data.people || [];
      if (!people.length) {
        return `<div class="empty">Chưa có người quen nào từ thông báo đám mây.</div>`;
      }
      const items = people
        .map(
          (person) => `<div class="item"><div class="avatar">${esc((person.name || "?").slice(0, 1).toUpperCase())}</div>
            <div class="grow"><div class="name">${esc(person.name || "Không rõ")}</div>
            <div class="meta">Lần cuối: ${esc(formatTime(person.notified_at))}</div></div>
            ${person.tag ? `<span class="badge ${esc(person.tag)}">${esc(tagLabel(person.tag))}</span>` : ""}</div>`
        )
        .join("");
      return `<section class="card"><h2>Người đã nhận diện</h2><div class="body list">${items}</div></section>`;
    }
    if (!data.catalog_available) {
      return `<div class="empty">Camera chưa trả về danh sách khuôn mặt. Kiểm tra kết nối nội bộ rồi làm mới.</div>`;
    }
    const writable = Boolean(data.face_write);
    const banner = writable
      ? ""
      : `<div class="banner warn"><div class="txt">
          <div class="title">Face ID chỉ đọc ở chế độ này</div>
          <div class="muted">Thêm, đổi tên, đổi nhóm và xoá cần kết nối nội bộ (không phải Tapo Control) và camera trả về danh sách khuôn mặt.</div>
        </div></div>`;
    const toolbar = `<div class="toolbar">
      ${writable ? `<button type="button" class="btn primary" data-action="face-add-open"${this._busy ? " disabled" : ""}>Thêm khuôn mặt</button>` : ""}
      <span class="spacer"></span>
      <button type="button" class="btn" data-action="refresh"${this._busy ? " disabled" : ""}>Làm mới</button></div>`;
    const faces = data.items || [];
    if (!faces.length) {
      return banner + toolbar + `<div class="empty">Camera chưa lưu khuôn mặt nào.</div>`;
    }
    const items = faces.map((face) => this._renderFaceItem(face, writable)).join("");
    const form = writable && this._faceAddOpen ? this._renderAddFaceForm() : "";
    return banner + toolbar + form + `<section class="card"><h2>Khuôn mặt đã lưu (${faces.length})</h2><div class="body list">${items}</div></section>`;
  }

  _renderAddFaceForm() {
    const disabled = this._busy ? " disabled" : "";
    return `<section class="card form-card"><h2>Thêm khuôn mặt</h2><div class="body">
      <div class="field"><label for="face-name">Tên</label>
        <input id="face-name" type="text" data-role="face-name" maxlength="32" placeholder="Ví dụ: An"${disabled}></div>
      <div class="field"><label for="face-tag-new">Nhóm</label>
        <select id="face-tag-new" data-role="face-tag-new"${disabled}>
          <option value="familiar">Người quen</option>
          <option value="stranger">Người lạ</option>
        </select></div>
      <div class="field"><label for="face-image">Ảnh chân dung (JPEG hoặc PNG)</label>
        <input id="face-image" type="file" accept="image/jpeg,image/png" data-role="face-image"${disabled}></div>
      <div class="actions">
        <button type="button" class="btn primary" data-action="face-add-submit"${disabled}>Thêm từ ảnh</button>
        <button type="button" class="btn" data-action="face-add-snapshot"${disabled}>Chụp từ camera</button>
        <button type="button" class="btn" data-action="face-add-cancel"${disabled}>Huỷ</button>
      </div>
    </div></section>`;
  }

  _renderFaceItem(face, writable) {
    const id = face.face_id;
    const initial = esc((face.name || "?").slice(0, 1).toUpperCase());
    const avatar = face.image_url
      ? `<div class="avatar"><img src="${esc(face.image_url)}" alt="" loading="lazy"></div>`
      : `<div class="avatar">${initial}</div>`;
    const disabled = this._busy ? " disabled" : "";
    const editing = writable && String(this._editingFace) === String(id);
    const confirming = writable && String(this._confirmDelete) === String(id);
    if (!writable) {
      const seen = face.last_seen ? `Lần cuối: ${esc(formatTime(face.last_seen))}` : "Chưa thấy gần đây";
      return `<div class="item">${avatar}<div class="grow">
        <div class="name">${esc(face.name || `Khuôn mặt ${esc(id)}`)}</div>
        <div class="meta">${esc(seen)}</div></div>
        ${face.tag ? `<span class="badge ${esc(face.tag)}">${esc(tagLabel(face.tag))}</span>` : ""}</div>`;
    }
    if (editing) {
      return `<div class="item">${avatar}
        <div class="grow"><input type="text" data-role="face-rename" maxlength="32" value="${esc(face.name || "")}" aria-label="Tên mới"${disabled}></div>
        <div class="face-actions">
          <button type="button" class="btn small primary" data-action="face-edit-save" data-face-id="${esc(id)}"${disabled}>Lưu</button>
          <button type="button" class="btn small" data-action="face-edit-cancel"${disabled}>Huỷ</button>
        </div></div>`;
    }
    if (confirming) {
      return `<div class="item">${avatar}
        <div class="grow"><div class="name">${esc(face.name || `Khuôn mặt ${esc(id)}`)}</div>
        <div class="meta">Xoá khuôn mặt này khỏi camera?</div></div>
        <div class="face-actions">
          <button type="button" class="btn small danger" data-action="face-delete-confirm" data-face-id="${esc(id)}"${disabled}>Xác nhận xoá</button>
          <button type="button" class="btn small" data-action="face-delete-cancel"${disabled}>Huỷ</button>
        </div></div>`;
    }
    const seen = face.last_seen ? `Lần cuối: ${esc(formatTime(face.last_seen))}` : "Chưa thấy gần đây";
    return `<div class="item">${avatar}
      <div class="grow"><div class="name">${esc(face.name || `Khuôn mặt ${esc(id)}`)}</div>
      <div class="meta">${esc(seen)}</div></div>
      <div class="face-actions">
        <select data-role="face-tag" data-face-id="${esc(id)}" aria-label="Nhóm của ${esc(face.name || id)}"${disabled}>
          <option value="familiar"${face.tag === "familiar" ? " selected" : ""}>Người quen</option>
          <option value="stranger"${face.tag === "stranger" ? " selected" : ""}>Người lạ</option>
        </select>
        <button type="button" class="btn small" data-action="face-edit" data-face-id="${esc(id)}"${disabled}>Đổi tên</button>
        <button type="button" class="btn small danger" data-action="face-delete" data-face-id="${esc(id)}"${disabled}>Xoá</button>
      </div></div>`;
  }

  _renderHistory() {
    const data = this._history;
    if (!data) return `<div class="loading">Đang tải…</div>`;
    const options = [`<option value="">Tất cả</option>`]
      .concat(HISTORY_TAGS.map((tag) => `<option value="${tag}"${tag === this._tag ? " selected" : ""}>${esc(tagLabel(tag))}</option>`))
      .join("");
    const toolbar = `<div class="toolbar"><select data-role="tag" aria-label="Lọc theo loại sự kiện">${options}</select>
      <span class="spacer"></span><button type="button" class="btn" data-action="refresh">Làm mới</button></div>`;
    const items = data.items || [];
    if (!items.length) {
      return toolbar + `<div class="empty">Chưa có sự kiện nào.</div>`;
    }
    const list = items
      .map(
        (event) => `<div class="item"><div class="grow">
          <div class="name">${esc(event.name || tagLabel(event.tag) || "Sự kiện")}</div>
          <div class="meta">${esc(formatTime(event.notified_at))}${event.source ? " · " + esc(event.source) : ""}</div></div>
          ${event.tag ? `<span class="badge ${esc(event.tag)}">${esc(tagLabel(event.tag))}</span>` : ""}</div>`
      )
      .join("");
    return toolbar + `<section class="card"><div class="body list">${list}</div></section>`;
  }

  _renderBody() {
    if (!this._cameras.length) {
      return `<div class="empty">Chưa có camera nào được cấu hình cho Tapo Connect.</div>`;
    }
    if (this._tab === "settings") return this._renderSettings();
    if (this._tab === "faces") return this._renderFaces();
    return this._renderHistory();
  }

  _render() {
    const toast = this._toast
      ? `<div class="toast ${this._toast.isError ? "error" : ""}" role="status">${esc(this._toast.message)}</div>`
      : "";
    this.shadowRoot.innerHTML = `
      <style>${css}</style>
      <div class="wrap">
        ${this._renderHeader()}
        ${this._renderTabs()}
        ${this._renderBanner()}
        ${this._renderBody()}
      </div>
      ${toast}
    `;
    this.shadowRoot.addEventListener("change", this._onChange);
    this.shadowRoot.addEventListener("click", this._onClick);
    const range = this.shadowRoot.querySelectorAll('input[type="range"]');
    range.forEach((element) => {
      element.addEventListener("input", () => {
        const output = element.parentElement.querySelector("output");
        if (output) output.textContent = element.value;
      });
    });
  }
}

if (!customElements.get("tapo-connect-panel")) {
  customElements.define("tapo-connect-panel", TapoConnectPanel);
}
