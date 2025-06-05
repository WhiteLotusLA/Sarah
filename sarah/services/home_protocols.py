"""Protocol handlers for smart home device communication."""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
import struct


@dataclass
class ProtocolMessage:
    """Generic protocol message structure."""

    device_id: str
    command: str
    payload: Dict[str, Any]
    timestamp: float


class DeviceProtocol(ABC):
    """Base class for device communication protocols."""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.message_handlers: List[Callable] = []
        self.connected = False

    @abstractmethod
    async def connect(self, **kwargs) -> bool:
        """Connect to the protocol service."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from the protocol service."""
        pass

    @abstractmethod
    async def send_command(
        self, device_id: str, command: str, params: Dict[str, Any]
    ) -> bool:
        """Send a command to a device."""
        pass

    @abstractmethod
    async def discover_devices(self) -> List[Dict[str, Any]]:
        """Discover devices using this protocol."""
        pass

    def add_message_handler(self, handler: Callable):
        """Add a handler for incoming messages."""
        self.message_handlers.append(handler)

    async def _handle_message(self, message: ProtocolMessage):
        """Handle incoming message."""
        for handler in self.message_handlers:
            try:
                await handler(message)
            except Exception as e:
                self.logger.error(f"Message handler error: {e}")


class MQTTProtocol(DeviceProtocol):
    """MQTT protocol handler for smart home devices."""

    def __init__(self):
        super().__init__("mqtt")
        self.client = None
        self.base_topic = "home"
        self.discovery_topic = "homeassistant"

    async def connect(
        self, host: str = "localhost", port: int = 1883, **kwargs
    ) -> bool:
        """Connect to MQTT broker."""
        try:
            import asyncio_mqtt

            self.client = asyncio_mqtt.Client(host, port)
            await self.client.connect()

            # Subscribe to device topics
            async with self.client.messages() as messages:
                await self.client.subscribe(f"{self.base_topic}/+/state")
                await self.client.subscribe(f"{self.base_topic}/+/attributes")
                await self.client.subscribe(f"{self.discovery_topic}/+/+/config")

                # Start message processing
                asyncio.create_task(self._process_messages(messages))

            self.connected = True
            self.logger.info(f"Connected to MQTT broker at {host}:{port}")
            return True

        except ImportError:
            self.logger.error("asyncio-mqtt not installed")
            return False
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT: {e}")
            return False

    async def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.client:
            await self.client.disconnect()
            self.connected = False
            self.logger.info("Disconnected from MQTT broker")

    async def send_command(
        self, device_id: str, command: str, params: Dict[str, Any]
    ) -> bool:
        """Send command to MQTT device."""
        if not self.connected or not self.client:
            return False

        try:
            topic = f"{self.base_topic}/{device_id}/set"
            payload = json.dumps({"command": command, **params})

            await self.client.publish(topic, payload)
            self.logger.debug(f"Sent MQTT command to {device_id}: {command}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send MQTT command: {e}")
            return False

    async def discover_devices(self) -> List[Dict[str, Any]]:
        """Discover MQTT devices using Home Assistant discovery protocol."""
        discovered = []

        if not self.connected:
            return discovered

        # Request device discovery
        try:
            await self.client.publish(f"{self.base_topic}/discovery/start", "1")

            # Wait for discovery responses
            await asyncio.sleep(5)

            # In practice, devices would be discovered through config messages
            # This is a simplified example

        except Exception as e:
            self.logger.error(f"MQTT discovery failed: {e}")

        return discovered

    async def _process_messages(self, messages):
        """Process incoming MQTT messages."""
        async for message in messages:
            try:
                topic_parts = message.topic.split("/")

                if len(topic_parts) >= 3 and topic_parts[0] == self.base_topic:
                    device_id = topic_parts[1]
                    message_type = topic_parts[2]

                    payload = json.loads(message.payload.decode())

                    msg = ProtocolMessage(
                        device_id=device_id,
                        command=message_type,
                        payload=payload,
                        timestamp=asyncio.get_event_loop().time(),
                    )

                    await self._handle_message(msg)

            except Exception as e:
                self.logger.error(f"Error processing MQTT message: {e}")


class ZigbeeProtocol(DeviceProtocol):
    """Zigbee protocol handler using zigbee2mqtt."""

    def __init__(self):
        super().__init__("zigbee")
        self.mqtt_client = None
        self.base_topic = "zigbee2mqtt"
        self.devices = {}

    async def connect(self, mqtt_host: str = "localhost", **kwargs) -> bool:
        """Connect to Zigbee network via zigbee2mqtt."""
        try:
            # Zigbee typically uses MQTT as transport
            self.mqtt_client = MQTTProtocol()
            connected = await self.mqtt_client.connect(mqtt_host)

            if connected:
                # Subscribe to Zigbee topics
                await self.mqtt_client.client.subscribe(f"{self.base_topic}/+")
                await self.mqtt_client.client.subscribe(
                    f"{self.base_topic}/bridge/devices"
                )
                self.connected = True
                self.logger.info("Connected to Zigbee network via zigbee2mqtt")

            return connected

        except Exception as e:
            self.logger.error(f"Failed to connect to Zigbee: {e}")
            return False

    async def disconnect(self):
        """Disconnect from Zigbee network."""
        if self.mqtt_client:
            await self.mqtt_client.disconnect()
            self.connected = False

    async def send_command(
        self, device_id: str, command: str, params: Dict[str, Any]
    ) -> bool:
        """Send command to Zigbee device."""
        if not self.connected or not self.mqtt_client:
            return False

        # Zigbee commands via MQTT
        topic = f"{self.base_topic}/{device_id}/set"

        # Convert command to Zigbee format
        zigbee_payload = self._convert_to_zigbee_format(command, params)

        return await self.mqtt_client.send_command(device_id, command, zigbee_payload)

    async def discover_devices(self) -> List[Dict[str, Any]]:
        """Discover Zigbee devices."""
        if not self.connected:
            return []

        # Request device list from zigbee2mqtt
        await self.mqtt_client.client.publish(
            f"{self.base_topic}/bridge/request/devices", "{}"
        )

        # Wait for response
        await asyncio.sleep(2)

        # Return discovered devices
        return list(self.devices.values())

    def _convert_to_zigbee_format(
        self, command: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert generic command to Zigbee format."""
        zigbee_commands = {
            "on": {"state": "ON"},
            "off": {"state": "OFF"},
            "brightness": {"brightness": params.get("level", 255)},
            "color": {
                "color": {
                    "r": params.get("r", 255),
                    "g": params.get("g", 255),
                    "b": params.get("b", 255),
                }
            },
            "temperature": {"color_temp": params.get("temp", 350)},
        }

        return zigbee_commands.get(command, params)


class HTTPProtocol(DeviceProtocol):
    """HTTP/REST API protocol handler."""

    def __init__(self):
        super().__init__("http")
        self.session = None

    async def connect(self, **kwargs) -> bool:
        """Initialize HTTP session."""
        try:
            import aiohttp

            self.session = aiohttp.ClientSession()
            self.connected = True
            self.logger.info("HTTP protocol handler initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize HTTP: {e}")
            return False

    async def disconnect(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.connected = False

    async def send_command(
        self, device_id: str, command: str, params: Dict[str, Any]
    ) -> bool:
        """Send HTTP command to device."""
        if not self.connected or not self.session:
            return False

        # Device should have stored endpoint URL
        device_config = params.get("_config", {})
        url = device_config.get("url")

        if not url:
            self.logger.error(f"No URL configured for device {device_id}")
            return False

        try:
            # Build request
            method = device_config.get("method", "POST")
            headers = device_config.get("headers", {})

            payload = {"command": command, **params}

            async with self.session.request(
                method, url, json=payload, headers=headers
            ) as response:
                if response.status == 200:
                    self.logger.debug(f"HTTP command sent to {device_id}")
                    return True
                else:
                    self.logger.error(f"HTTP command failed: {response.status}")
                    return False

        except Exception as e:
            self.logger.error(f"HTTP request failed: {e}")
            return False

    async def discover_devices(self) -> List[Dict[str, Any]]:
        """Discover HTTP devices (not typically discoverable)."""
        # HTTP devices usually need manual configuration
        return []


class ProtocolManager:
    """Manages multiple device protocols."""

    def __init__(self):
        self.protocols: Dict[str, DeviceProtocol] = {}
        self.logger = logging.getLogger(__name__)

    async def initialize_protocols(self, config: Dict[str, Any]):
        """Initialize configured protocols."""
        # MQTT
        if config.get("mqtt", {}).get("enabled", True):
            mqtt = MQTTProtocol()
            if await mqtt.connect(**config.get("mqtt", {})):
                self.protocols["mqtt"] = mqtt

        # Zigbee
        if config.get("zigbee", {}).get("enabled", False):
            zigbee = ZigbeeProtocol()
            if await zigbee.connect(**config.get("zigbee", {})):
                self.protocols["zigbee"] = zigbee

        # HTTP
        if config.get("http", {}).get("enabled", True):
            http = HTTPProtocol()
            if await http.connect():
                self.protocols["http"] = http

        self.logger.info(f"Initialized protocols: {list(self.protocols.keys())}")

    async def send_command(
        self, protocol: str, device_id: str, command: str, params: Dict[str, Any]
    ) -> bool:
        """Send command using specified protocol."""
        if protocol not in self.protocols:
            self.logger.error(f"Protocol {protocol} not available")
            return False

        return await self.protocols[protocol].send_command(device_id, command, params)

    async def discover_all_devices(self) -> Dict[str, List[Dict[str, Any]]]:
        """Discover devices across all protocols."""
        discoveries = {}

        for name, protocol in self.protocols.items():
            try:
                devices = await protocol.discover_devices()
                discoveries[name] = devices
            except Exception as e:
                self.logger.error(f"Discovery failed for {name}: {e}")
                discoveries[name] = []

        return discoveries

    def add_message_handler(self, protocol: str, handler: Callable):
        """Add message handler for specific protocol."""
        if protocol in self.protocols:
            self.protocols[protocol].add_message_handler(handler)

    async def shutdown(self):
        """Shutdown all protocols."""
        for protocol in self.protocols.values():
            try:
                await protocol.disconnect()
            except Exception as e:
                self.logger.error(f"Error disconnecting {protocol.name}: {e}")
