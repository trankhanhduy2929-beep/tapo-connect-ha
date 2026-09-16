"""Actual face names and notification timestamps from Tapo cloud messages."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .notification_data import CORE_CATEGORIES, NOTIFICATION_CATEGORIES


async def async_setup_notification_sensors(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["notification_coordinator"]
    async_add_entities([NotificationSensor(coordinator, key) for key in ("cloud_face_name", "cloud_face_time", "cloud_face_type")])
    added = set()
    categories_added = set()
    async_add_entities([NotificationCategorySensor(coordinator, "latest_time"), NotificationCategorySensor(coordinator, "latest_type")])

    @callback
    def add_people():
        entities = []
        for person_key in coordinator.history.people:
            if person_key not in added:
                added.add(person_key)
                entities.append(NotificationSensor(coordinator, "cloud_person_time", person_key))
        for category in dict.fromkeys([*CORE_CATEGORIES, *coordinator.history.categories]):
            if category not in categories_added:
                categories_added.add(category)
                entities.append(NotificationCategorySensor(coordinator, category))
        if entities:
            async_add_entities(entities)

    add_people()
    entry.async_on_unload(coordinator.async_add_listener(add_people))


class NotificationSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator, key: str, person_key: str | None = None):
        super().__init__(coordinator)
        self.key = key
        self.person_key = person_key
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.device_id}_{key}" + (f"_{person_key}" if person_key else "")
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.device_id)}, manufacturer="TP-Link", model="C260", name="Tapo C260")
        if key in ("cloud_face_time", "cloud_person_time"):
            self._attr_device_class = "timestamp"
        if key == "cloud_face_type":
            self._attr_device_class = "enum"
            self._attr_options = ["familiar", "stranger"]
        if person_key:
            self._attr_translation_placeholders = {"person": coordinator.history.people[person_key]["name"]}

    @property
    def suggested_object_id(self):
        if self.person_key:
            return f"cloud_person_{self.person_key}_last_notified"
        return super().suggested_object_id

    @property
    def event(self):
        return self.coordinator.history.people.get(self.person_key) if self.person_key else self.coordinator.history.latest

    @property
    def native_value(self):
        event = self.event or {}
        return event.get("name" if self.key == "cloud_face_name" else "tag" if self.key == "cloud_face_type" else "notified_at")

    @property
    def extra_state_attributes(self):
        event = self.event or {}
        return {"source": "tapo_cloud_notification", "time_source": "notification.time", "person_name": event.get("name"), "face_id": event.get("face_id"), "identity_source": "personName" if self.person_key else "notification", "history_truncated": self.coordinator.history.truncated, "poll_interval_seconds": self.coordinator.update_interval.total_seconds()}


class NotificationCategorySensor(NotificationSensor):
    def __init__(self, coordinator, category):
        self.category = category
        super().__init__(coordinator, f"cloud_notification_{category}")
        self._attr_device_class = "timestamp"
        if category == "latest_type":
            self._attr_device_class = "enum"
            self._attr_options = list(NOTIFICATION_CATEGORIES)

    @property
    def event(self):
        if self.category in {"latest_type", "latest_time"}:
            return self.coordinator.history.latest_notification
        return self.coordinator.history.categories.get(self.category)

    @property
    def native_value(self):
        return (self.event or {}).get("tag" if self.category == "latest_type" else "notified_at")

    @property
    def extra_state_attributes(self):
        return {**super().extra_state_attributes, "message_type": (self.event or {}).get("message_type"), "presence_sensor": False}
