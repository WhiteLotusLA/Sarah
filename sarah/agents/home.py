"""Home automation agent for smart home device control and automation."""

import asyncio
import json
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, time, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging

from sarah.agents.base import BaseAgent
from sarah.services.home_protocols import ProtocolManager, ProtocolMessage


class DeviceType(Enum):
    """Types of smart home devices."""

    LIGHT = "light"
    SWITCH = "switch"
    THERMOSTAT = "thermostat"
    LOCK = "lock"
    SENSOR = "sensor"
    CAMERA = "camera"
    SPEAKER = "speaker"
    VACUUM = "vacuum"
    SHADE = "shade"
    FAN = "fan"
    PLUG = "plug"
    DOORBELL = "doorbell"
    GARAGE = "garage"


class DeviceState(Enum):
    """Common device states."""

    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


@dataclass
class Device:
    """Represents a smart home device."""

    id: str
    name: str
    type: DeviceType
    room: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    state: DeviceState = DeviceState.UNKNOWN
    attributes: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    last_seen: Optional[datetime] = None
    protocol: Optional[str] = None  # mqtt, zigbee, zwave, wifi, etc.


@dataclass
class Scene:
    """Represents a home automation scene."""

    id: str
    name: str
    description: Optional[str] = None
    devices: Dict[str, Dict[str, Any]] = field(
        default_factory=dict
    )  # device_id -> state/attributes
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class AutomationRule:
    """Represents an automation rule."""

    id: str
    name: str
    enabled: bool = True
    triggers: List[Dict[str, Any]] = field(default_factory=list)
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    last_triggered: Optional[datetime] = None


class HomeAgent(BaseAgent):
    """Agent for managing smart home devices and automation."""

    def __init__(self, agent_id: str = "home_agent"):
        super().__init__(agent_id, agent_type="automation")
        self.devices: Dict[str, Device] = {}
        self.scenes: Dict[str, Scene] = {}
        self.automations: Dict[str, AutomationRule] = {}
        self.device_handlers: Dict[str, Callable] = {}
        self.protocol_manager = ProtocolManager()
        self.running_automations: Dict[str, asyncio.Task] = {}

    async def initialize(self):
        """Initialize the home automation agent."""
        await super().initialize()

        # Initialize device protocols
        await self._initialize_protocols()

        # Start device discovery
        asyncio.create_task(self._device_discovery_loop())

        # Start automation engine
        asyncio.create_task(self._automation_engine_loop())

        self.logger.info("Home automation agent initialized")

    async def _initialize_protocols(self):
        """Initialize communication protocols for devices."""
        protocol_config = {
            "mqtt": {"enabled": True, "host": "localhost", "port": 1883},
            "zigbee": {
                "enabled": False,  # Enable if zigbee2mqtt is available
                "mqtt_host": "localhost",
            },
            "http": {"enabled": True},
        }

        await self.protocol_manager.initialize_protocols(protocol_config)

        # Set up message handlers
        for protocol in self.protocol_manager.protocols:
            self.protocol_manager.add_message_handler(
                protocol, self._handle_protocol_message
            )

    async def handle_command(
        self, command: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle home automation commands."""
        try:
            if command == "list_devices":
                return await self.list_devices(data.get("room"), data.get("type"))

            elif command == "control_device":
                device_id = data.get("device_id")
                action = data.get("action")
                attributes = data.get("attributes", {})
                return await self.control_device(device_id, action, attributes)

            elif command == "create_scene":
                name = data.get("name")
                devices = data.get("devices", {})
                description = data.get("description")
                return await self.create_scene(name, devices, description)

            elif command == "activate_scene":
                scene_id = data.get("scene_id")
                return await self.activate_scene(scene_id)

            elif command == "create_automation":
                rule_data = data.get("rule", {})
                return await self.create_automation(rule_data)

            elif command == "toggle_automation":
                automation_id = data.get("automation_id")
                enabled = data.get("enabled")
                return await self.toggle_automation(automation_id, enabled)

            elif command == "get_device_status":
                device_id = data.get("device_id")
                return await self.get_device_status(device_id)

            elif command == "discover_devices":
                return await self.discover_devices()

            else:
                return {"error": f"Unknown command: {command}"}

        except Exception as e:
            self.logger.error(f"Error handling command {command}: {e}")
            return {"error": str(e)}

    async def register_device(self, device: Device) -> bool:
        """Register a new device."""
        if device.id in self.devices:
            self.logger.warning(f"Device {device.id} already registered")
            return False

        self.devices[device.id] = device
        device.last_seen = datetime.now()

        # Send device registration event
        await self.send_message(
            {
                "type": "device_registered",
                "device": {
                    "id": device.id,
                    "name": device.name,
                    "type": device.type.value,
                    "room": device.room,
                    "state": device.state.value,
                },
            },
            "director_agent",
        )

        self.logger.info(f"Registered device: {device.name} ({device.type.value})")
        return True

    async def control_device(
        self, device_id: str, action: str, attributes: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Control a specific device."""
        if device_id not in self.devices:
            return {"error": f"Device {device_id} not found"}

        device = self.devices[device_id]
        attributes = attributes or {}

        try:
            # Handle common actions
            if action == "turn_on":
                device.state = DeviceState.ON
                result = await self._send_device_command(device, "on", attributes)

            elif action == "turn_off":
                device.state = DeviceState.OFF
                result = await self._send_device_command(device, "off", attributes)

            elif action == "toggle":
                new_state = (
                    DeviceState.OFF
                    if device.state == DeviceState.ON
                    else DeviceState.ON
                )
                device.state = new_state
                result = await self._send_device_command(
                    device, new_state.value, attributes
                )

            elif action == "set_brightness" and device.type == DeviceType.LIGHT:
                brightness = attributes.get("brightness", 100)
                device.attributes["brightness"] = brightness
                result = await self._send_device_command(
                    device, "brightness", {"level": brightness}
                )

            elif action == "set_temperature" and device.type == DeviceType.THERMOSTAT:
                temperature = attributes.get("temperature")
                if temperature:
                    device.attributes["target_temperature"] = temperature
                    result = await self._send_device_command(
                        device, "set_temperature", {"temp": temperature}
                    )
                else:
                    return {"error": "Temperature not specified"}

            elif action == "lock" and device.type == DeviceType.LOCK:
                device.state = DeviceState.ON  # ON = locked
                result = await self._send_device_command(device, "lock", {})

            elif action == "unlock" and device.type == DeviceType.LOCK:
                device.state = DeviceState.OFF  # OFF = unlocked
                result = await self._send_device_command(device, "unlock", {})

            else:
                # Custom action
                result = await self._send_device_command(device, action, attributes)

            device.last_seen = datetime.now()

            return {
                "success": True,
                "device_id": device_id,
                "action": action,
                "new_state": device.state.value,
                "attributes": device.attributes,
            }

        except Exception as e:
            self.logger.error(f"Failed to control device {device_id}: {e}")
            return {"error": f"Failed to control device: {str(e)}"}

    async def _send_device_command(
        self, device: Device, command: str, params: Dict[str, Any]
    ) -> Any:
        """Send command to physical device."""
        if not device.protocol:
            self.logger.warning(f"No protocol specified for device {device.id}")
            return False

        # Add device configuration to params
        params["_config"] = device.attributes.get("config", {})

        success = await self.protocol_manager.send_command(
            device.protocol, device.id, command, params
        )

        if not success:
            self.logger.error(f"Failed to send command to device {device.id}")

        return success

    async def list_devices(
        self, room: Optional[str] = None, device_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all devices, optionally filtered by room or type."""
        devices = []

        for device in self.devices.values():
            # Apply filters
            if room and device.room != room:
                continue
            if device_type and device.type.value != device_type:
                continue

            devices.append(
                {
                    "id": device.id,
                    "name": device.name,
                    "type": device.type.value,
                    "room": device.room,
                    "state": device.state.value,
                    "attributes": device.attributes,
                    "last_seen": (
                        device.last_seen.isoformat() if device.last_seen else None
                    ),
                }
            )

        return {
            "devices": devices,
            "count": len(devices),
            "filters": {"room": room, "type": device_type},
        }

    async def create_scene(
        self,
        name: str,
        devices: Dict[str, Dict[str, Any]],
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new scene."""
        scene_id = f"scene_{len(self.scenes) + 1}"

        scene = Scene(id=scene_id, name=name, description=description, devices=devices)

        self.scenes[scene_id] = scene

        return {
            "success": True,
            "scene_id": scene_id,
            "name": name,
            "device_count": len(devices),
        }

    async def activate_scene(self, scene_id: str) -> Dict[str, Any]:
        """Activate a scene."""
        if scene_id not in self.scenes:
            return {"error": f"Scene {scene_id} not found"}

        scene = self.scenes[scene_id]
        results = []

        for device_id, state_config in scene.devices.items():
            action = state_config.get("action", "turn_on")
            attributes = state_config.get("attributes", {})

            result = await self.control_device(device_id, action, attributes)
            results.append(
                {"device_id": device_id, "success": result.get("success", False)}
            )

        return {
            "success": True,
            "scene_id": scene_id,
            "scene_name": scene.name,
            "devices_activated": len(results),
            "results": results,
        }

    async def create_automation(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new automation rule."""
        automation_id = f"automation_{len(self.automations) + 1}"

        automation = AutomationRule(
            id=automation_id,
            name=rule_data.get("name", f"Automation {automation_id}"),
            triggers=rule_data.get("triggers", []),
            conditions=rule_data.get("conditions", []),
            actions=rule_data.get("actions", []),
            enabled=rule_data.get("enabled", True),
        )

        self.automations[automation_id] = automation

        return {
            "success": True,
            "automation_id": automation_id,
            "name": automation.name,
            "enabled": automation.enabled,
        }

    async def toggle_automation(
        self, automation_id: str, enabled: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Enable or disable an automation."""
        if automation_id not in self.automations:
            return {"error": f"Automation {automation_id} not found"}

        automation = self.automations[automation_id]

        if enabled is None:
            automation.enabled = not automation.enabled
        else:
            automation.enabled = enabled

        return {
            "success": True,
            "automation_id": automation_id,
            "enabled": automation.enabled,
        }

    async def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """Get detailed status of a device."""
        if device_id not in self.devices:
            return {"error": f"Device {device_id} not found"}

        device = self.devices[device_id]

        return {
            "device_id": device.id,
            "name": device.name,
            "type": device.type.value,
            "room": device.room,
            "state": device.state.value,
            "attributes": device.attributes,
            "capabilities": device.capabilities,
            "manufacturer": device.manufacturer,
            "model": device.model,
            "protocol": device.protocol,
            "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            "online": (
                (datetime.now() - device.last_seen).seconds < 300
                if device.last_seen
                else False
            ),
        }

    async def discover_devices(self) -> Dict[str, Any]:
        """Manually trigger device discovery."""
        discovered = await self._perform_device_discovery()

        return {
            "success": True,
            "discovered_count": len(discovered),
            "devices": discovered,
        }

    async def _device_discovery_loop(self):
        """Background task for automatic device discovery."""
        while self.state == "running":
            try:
                await self._perform_device_discovery()
                await asyncio.sleep(300)  # Discover every 5 minutes
            except Exception as e:
                self.logger.error(f"Device discovery error: {e}")
                await asyncio.sleep(60)

    async def _perform_device_discovery(self) -> List[Dict[str, Any]]:
        """Perform device discovery across protocols."""
        all_discovered = []

        # Discover devices from all protocols
        discoveries = await self.protocol_manager.discover_all_devices()

        for protocol, devices in discoveries.items():
            for device_info in devices:
                # Convert protocol-specific device info to our Device model
                device = self._create_device_from_discovery(device_info, protocol)
                if device and device.id not in self.devices:
                    await self.register_device(device)
                    all_discovered.append(
                        {
                            "id": device.id,
                            "name": device.name,
                            "type": device.type.value,
                            "protocol": protocol,
                        }
                    )

        # Also include some example devices for testing
        example_devices = [
            Device(
                id="light_living_room_1",
                name="Living Room Light",
                type=DeviceType.LIGHT,
                room="Living Room",
                manufacturer="Philips",
                model="Hue White",
                capabilities=["on_off", "brightness", "color_temp"],
                protocol="zigbee",
            ),
            Device(
                id="thermostat_main",
                name="Main Thermostat",
                type=DeviceType.THERMOSTAT,
                room="Hallway",
                manufacturer="Nest",
                model="Learning Thermostat",
                capabilities=["temperature", "humidity", "schedule"],
                protocol="http",
                attributes={
                    "config": {
                        "url": "http://192.168.1.100/api",
                        "method": "POST",
                        "headers": {"Authorization": "Bearer token"},
                    }
                },
            ),
            Device(
                id="lock_front_door",
                name="Front Door Lock",
                type=DeviceType.LOCK,
                room="Entrance",
                manufacturer="August",
                model="Smart Lock Pro",
                capabilities=["lock", "unlock", "auto_lock"],
                protocol="mqtt",
            ),
        ]

        for device in example_devices:
            if device.id not in self.devices:
                await self.register_device(device)
                all_discovered.append(
                    {
                        "id": device.id,
                        "name": device.name,
                        "type": device.type.value,
                        "protocol": device.protocol,
                    }
                )

        return all_discovered

    def _create_device_from_discovery(
        self, device_info: Dict[str, Any], protocol: str
    ) -> Optional[Device]:
        """Create Device object from protocol discovery data."""
        try:
            # Map common device types
            type_mapping = {
                "light": DeviceType.LIGHT,
                "switch": DeviceType.SWITCH,
                "sensor": DeviceType.SENSOR,
                "thermostat": DeviceType.THERMOSTAT,
                "lock": DeviceType.LOCK,
                "camera": DeviceType.CAMERA,
            }

            device_type = type_mapping.get(
                device_info.get("type", "").lower(), DeviceType.SWITCH
            )

            return Device(
                id=device_info.get("id", f"unknown_{protocol}"),
                name=device_info.get("name", "Unknown Device"),
                type=device_type,
                room=device_info.get("location"),
                manufacturer=device_info.get("manufacturer"),
                model=device_info.get("model"),
                capabilities=device_info.get("features", []),
                protocol=protocol,
                attributes=device_info.get("attributes", {}),
            )
        except Exception as e:
            self.logger.error(f"Failed to create device from discovery: {e}")
            return None

    async def _handle_protocol_message(self, message: ProtocolMessage):
        """Handle incoming messages from protocols."""
        device_id = message.device_id

        if device_id in self.devices:
            device = self.devices[device_id]

            # Update device state based on message
            if message.command == "state":
                new_state = message.payload.get("state", "").lower()
                if new_state in ["on", "off"]:
                    device.state = (
                        DeviceState.ON if new_state == "on" else DeviceState.OFF
                    )

            elif message.command == "attributes":
                device.attributes.update(message.payload)

            device.last_seen = datetime.now()

            # Notify about device update
            await self.send_message(
                {
                    "type": "device_update",
                    "device_id": device_id,
                    "state": device.state.value,
                    "attributes": device.attributes,
                },
                "director_agent",
            )

    async def _automation_engine_loop(self):
        """Background task for processing automation rules."""
        while self.state == "running":
            try:
                await self._check_automations()
                await asyncio.sleep(1)  # Check every second
            except Exception as e:
                self.logger.error(f"Automation engine error: {e}")
                await asyncio.sleep(5)

    async def _check_automations(self):
        """Check and execute automation rules."""
        for automation in self.automations.values():
            if not automation.enabled:
                continue

            # Check if any trigger is met
            for trigger in automation.triggers:
                if await self._evaluate_trigger(trigger):
                    # Check all conditions
                    conditions_met = all(
                        await self._evaluate_condition(condition)
                        for condition in automation.conditions
                    )

                    if conditions_met:
                        # Execute actions
                        await self._execute_automation_actions(automation)
                        automation.last_triggered = datetime.now()
                        break

    async def _evaluate_trigger(self, trigger: Dict[str, Any]) -> bool:
        """Evaluate if a trigger condition is met."""
        trigger_type = trigger.get("type")

        if trigger_type == "time":
            # Time-based trigger
            trigger_time = time.fromisoformat(trigger.get("at", "00:00"))
            now = datetime.now().time()
            # Check if within 1 minute of trigger time
            return (
                abs(
                    (now.hour * 60 + now.minute)
                    - (trigger_time.hour * 60 + trigger_time.minute)
                )
                < 1
            )

        elif trigger_type == "device_state":
            # Device state change trigger
            device_id = trigger.get("device_id")
            expected_state = trigger.get("state")

            if device_id in self.devices:
                return self.devices[device_id].state.value == expected_state

        elif trigger_type == "sun":
            # Sunrise/sunset trigger (would need location data)
            event = trigger.get("event")  # "sunrise" or "sunset"
            # Simplified - would calculate based on location
            return False

        return False

    async def _evaluate_condition(self, condition: Dict[str, Any]) -> bool:
        """Evaluate if a condition is met."""
        condition_type = condition.get("type")

        if condition_type == "device_state":
            device_id = condition.get("device_id")
            expected_state = condition.get("state")

            if device_id in self.devices:
                return self.devices[device_id].state.value == expected_state

        elif condition_type == "time_range":
            start_time = time.fromisoformat(condition.get("after", "00:00"))
            end_time = time.fromisoformat(condition.get("before", "23:59"))
            now = datetime.now().time()

            return start_time <= now <= end_time

        return True  # Default to true if condition type unknown

    async def _execute_automation_actions(self, automation: AutomationRule):
        """Execute automation actions."""
        for action in automation.actions:
            action_type = action.get("type")

            if action_type == "device_action":
                device_id = action.get("device_id")
                command = action.get("action")
                attributes = action.get("attributes", {})

                await self.control_device(device_id, command, attributes)

            elif action_type == "scene":
                scene_id = action.get("scene_id")
                await self.activate_scene(scene_id)

            elif action_type == "notification":
                message = action.get("message")
                await self.send_message(
                    {
                        "type": "automation_notification",
                        "automation_id": automation.id,
                        "automation_name": automation.name,
                        "message": message,
                    },
                    "director_agent",
                )

            elif action_type == "delay":
                delay_seconds = action.get("seconds", 0)
                await asyncio.sleep(delay_seconds)

    async def process_message(self, message: Dict[str, Any]):
        """Process incoming messages."""
        message_type = message.get("type", "")

        if message_type == "home_command":
            command = message.get("command", "")
            data = message.get("data", {})

            result = await self.handle_command(command, data)

            await self.send_message(
                {
                    "type": "home_response",
                    "request_id": message.get("request_id"),
                    "result": result,
                },
                message.get("sender"),
            )

        elif message_type == "device_event":
            # Handle device state updates from external sources
            device_id = message.get("device_id")
            if device_id in self.devices:
                device = self.devices[device_id]
                device.state = DeviceState(message.get("state", "unknown"))
                device.attributes.update(message.get("attributes", {}))
                device.last_seen = datetime.now()

    async def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        status = await super().get_status()
        status.update(
            {
                "device_count": len(self.devices),
                "online_devices": sum(
                    1
                    for d in self.devices.values()
                    if d.last_seen and (datetime.now() - d.last_seen).seconds < 300
                ),
                "scene_count": len(self.scenes),
                "automation_count": len(self.automations),
                "active_automations": sum(
                    1 for a in self.automations.values() if a.enabled
                ),
                "protocols_active": [
                    "mqtt",
                    "http",
                    "zigbee",
                    "wifi",
                    "bluetooth",
                ],  # Example
            }
        )
        return status
