"""Tests for Home automation agent."""

import pytest
import asyncio
from datetime import datetime, time
from unittest.mock import Mock, AsyncMock, patch

from sarah.agents.home import (
    HomeAgent,
    Device,
    DeviceType,
    DeviceState,
    Scene,
    AutomationRule,
)
from sarah.services.home_protocols import ProtocolManager, ProtocolMessage


class TestHomeAgent:
    """Test suite for HomeAgent."""

    @pytest.fixture
    def home_agent(self):
        """Create a HomeAgent instance for testing."""
        agent = HomeAgent("test_home_agent")
        return agent

    @pytest.fixture
    def sample_device(self):
        """Create a sample device for testing."""
        return Device(
            id="test_light_1",
            name="Test Light",
            type=DeviceType.LIGHT,
            room="Living Room",
            manufacturer="Test Corp",
            model="Light v1",
            capabilities=["on_off", "brightness"],
            protocol="mqtt",
        )

    @pytest.mark.asyncio
    async def test_initialization(self, home_agent):
        """Test agent initialization."""
        with patch.object(
            home_agent.protocol_manager, "initialize_protocols"
        ) as mock_init:
            await home_agent.initialize()

            assert home_agent.state == "running"
            assert len(home_agent.devices) == 0
            assert len(home_agent.scenes) == 0
            assert len(home_agent.automations) == 0
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_device(self, home_agent, sample_device):
        """Test device registration."""
        await home_agent.initialize()

        with patch.object(home_agent, "send_message") as mock_send:
            result = await home_agent.register_device(sample_device)

            assert result is True
            assert sample_device.id in home_agent.devices
            assert home_agent.devices[sample_device.id] == sample_device
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_control_device_turn_on(self, home_agent, sample_device):
        """Test turning a device on."""
        await home_agent.initialize()
        await home_agent.register_device(sample_device)

        with patch.object(home_agent, "_send_device_command") as mock_send:
            mock_send.return_value = True

            result = await home_agent.control_device(sample_device.id, "turn_on")

            assert result["success"] is True
            assert result["action"] == "turn_on"
            assert home_agent.devices[sample_device.id].state == DeviceState.ON
            mock_send.assert_called_once_with(sample_device, "on", {})

    @pytest.mark.asyncio
    async def test_control_device_brightness(self, home_agent, sample_device):
        """Test setting device brightness."""
        await home_agent.initialize()
        await home_agent.register_device(sample_device)

        with patch.object(home_agent, "_send_device_command") as mock_send:
            mock_send.return_value = True

            result = await home_agent.control_device(
                sample_device.id, "set_brightness", {"brightness": 50}
            )

            assert result["success"] is True
            assert home_agent.devices[sample_device.id].attributes["brightness"] == 50

    @pytest.mark.asyncio
    async def test_list_devices(self, home_agent):
        """Test listing devices."""
        await home_agent.initialize()

        # Add multiple devices
        devices = [
            Device(
                id="light1", name="Light 1", type=DeviceType.LIGHT, room="Living Room"
            ),
            Device(id="lock1", name="Lock 1", type=DeviceType.LOCK, room="Entrance"),
            Device(id="light2", name="Light 2", type=DeviceType.LIGHT, room="Bedroom"),
        ]

        for device in devices:
            await home_agent.register_device(device)

        # Test listing all devices
        result = await home_agent.list_devices()
        assert result["count"] == 3

        # Test filtering by room
        result = await home_agent.list_devices(room="Living Room")
        assert result["count"] == 1
        assert result["devices"][0]["id"] == "light1"

        # Test filtering by type
        result = await home_agent.list_devices(device_type="light")
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_create_scene(self, home_agent):
        """Test creating a scene."""
        await home_agent.initialize()

        scene_devices = {
            "light1": {"action": "turn_on", "attributes": {"brightness": 80}},
            "light2": {"action": "turn_off"},
        }

        result = await home_agent.create_scene(
            "Evening Scene", scene_devices, "Relaxing evening setup"
        )

        assert result["success"] is True
        assert result["scene_id"] in home_agent.scenes

        scene = home_agent.scenes[result["scene_id"]]
        assert scene.name == "Evening Scene"
        assert len(scene.devices) == 2

    @pytest.mark.asyncio
    async def test_activate_scene(self, home_agent):
        """Test activating a scene."""
        await home_agent.initialize()

        # Register devices
        devices = [
            Device(id="light1", name="Light 1", type=DeviceType.LIGHT),
            Device(id="light2", name="Light 2", type=DeviceType.LIGHT),
        ]
        for device in devices:
            await home_agent.register_device(device)

        # Create scene
        scene_devices = {
            "light1": {"action": "turn_on"},
            "light2": {"action": "turn_off"},
        }
        result = await home_agent.create_scene("Test Scene", scene_devices)
        scene_id = result["scene_id"]

        # Activate scene
        with patch.object(home_agent, "_send_device_command") as mock_send:
            mock_send.return_value = True

            result = await home_agent.activate_scene(scene_id)

            assert result["success"] is True
            assert result["devices_activated"] == 2
            assert mock_send.call_count == 2

    @pytest.mark.asyncio
    async def test_create_automation(self, home_agent):
        """Test creating an automation rule."""
        await home_agent.initialize()

        rule_data = {
            "name": "Sunset Lights",
            "triggers": [{"type": "sun", "event": "sunset"}],
            "conditions": [{"type": "time_range", "after": "17:00", "before": "23:00"}],
            "actions": [
                {"type": "device_action", "device_id": "light1", "action": "turn_on"}
            ],
        }

        result = await home_agent.create_automation(rule_data)

        assert result["success"] is True
        assert result["automation_id"] in home_agent.automations

        automation = home_agent.automations[result["automation_id"]]
        assert automation.name == "Sunset Lights"
        assert len(automation.triggers) == 1
        assert len(automation.actions) == 1

    @pytest.mark.asyncio
    async def test_toggle_automation(self, home_agent):
        """Test enabling/disabling automation."""
        await home_agent.initialize()

        # Create automation
        rule_data = {"name": "Test Automation"}
        result = await home_agent.create_automation(rule_data)
        automation_id = result["automation_id"]

        # Toggle off
        result = await home_agent.toggle_automation(automation_id, False)
        assert result["success"] is True
        assert result["enabled"] is False

        # Toggle on
        result = await home_agent.toggle_automation(automation_id, True)
        assert result["success"] is True
        assert result["enabled"] is True

    @pytest.mark.asyncio
    async def test_device_discovery(self, home_agent):
        """Test device discovery."""
        await home_agent.initialize()

        with patch.object(
            home_agent.protocol_manager, "discover_all_devices"
        ) as mock_discover:
            mock_discover.return_value = {
                "mqtt": [
                    {
                        "id": "mqtt_device_1",
                        "name": "MQTT Light",
                        "type": "light",
                        "features": ["on_off", "brightness"],
                    }
                ]
            }

            result = await home_agent.discover_devices()

            assert result["success"] is True
            # Should include discovered + example devices
            assert result["discovered_count"] >= 1

    @pytest.mark.asyncio
    async def test_automation_time_trigger(self, home_agent):
        """Test time-based automation trigger."""
        await home_agent.initialize()

        # Mock current time
        current_time = time(10, 0)  # 10:00 AM

        trigger = {"type": "time", "at": "10:00"}

        with patch("sarah.agents.home.datetime") as mock_datetime:
            mock_datetime.now.return_value.time.return_value = current_time

            result = await home_agent._evaluate_trigger(trigger)
            assert result is True

            # Test non-matching time
            trigger["at"] = "15:00"
            result = await home_agent._evaluate_trigger(trigger)
            assert result is False

    @pytest.mark.asyncio
    async def test_automation_device_state_trigger(self, home_agent, sample_device):
        """Test device state automation trigger."""
        await home_agent.initialize()
        await home_agent.register_device(sample_device)

        sample_device.state = DeviceState.ON

        trigger = {"type": "device_state", "device_id": sample_device.id, "state": "on"}

        result = await home_agent._evaluate_trigger(trigger)
        assert result is True

        # Test non-matching state
        trigger["state"] = "off"
        result = await home_agent._evaluate_trigger(trigger)
        assert result is False

    @pytest.mark.asyncio
    async def test_protocol_message_handling(self, home_agent, sample_device):
        """Test handling protocol messages."""
        await home_agent.initialize()
        await home_agent.register_device(sample_device)

        # Create state update message
        message = ProtocolMessage(
            device_id=sample_device.id,
            command="state",
            payload={"state": "on"},
            timestamp=0,
        )

        with patch.object(home_agent, "send_message") as mock_send:
            await home_agent._handle_protocol_message(message)

            assert home_agent.devices[sample_device.id].state == DeviceState.ON
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_status(self, home_agent):
        """Test getting agent status."""
        await home_agent.initialize()

        # Add some devices and automations
        device = Device(id="d1", name="Device 1", type=DeviceType.LIGHT)
        device.last_seen = datetime.now()
        await home_agent.register_device(device)

        await home_agent.create_automation({"name": "Auto 1"})

        status = await home_agent.get_status()

        assert status["agent_id"] == "test_home_agent"
        assert status["state"] == "running"
        assert status["device_count"] == 1
        assert status["online_devices"] == 1
        assert status["automation_count"] == 1
        assert status["active_automations"] == 1


class TestDeviceProtocols:
    """Test device protocol handlers."""

    @pytest.mark.asyncio
    async def test_protocol_manager_initialization(self):
        """Test protocol manager initialization."""
        from sarah.services.home_protocols import ProtocolManager

        manager = ProtocolManager()

        config = {"mqtt": {"enabled": False}, "http": {"enabled": True}}

        with patch(
            "sarah.services.home_protocols.HTTPProtocol.connect"
        ) as mock_connect:
            mock_connect.return_value = True

            await manager.initialize_protocols(config)

            assert "http" in manager.protocols
            assert "mqtt" not in manager.protocols

    @pytest.mark.asyncio
    async def test_mqtt_protocol_command(self):
        """Test MQTT protocol command sending."""
        from sarah.services.home_protocols import MQTTProtocol

        protocol = MQTTProtocol()
        protocol.connected = True
        protocol.client = Mock()
        protocol.client.publish = AsyncMock()

        result = await protocol.send_command("device1", "turn_on", {"brightness": 100})

        assert result is True
        protocol.client.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_protocol_command(self):
        """Test HTTP protocol command sending."""
        from sarah.services.home_protocols import HTTPProtocol

        protocol = HTTPProtocol()
        protocol.connected = True

        # Mock session
        mock_response = Mock()
        mock_response.status = 200

        mock_session = Mock()
        mock_session.request = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        protocol.session = mock_session

        result = await protocol.send_command(
            "device1",
            "turn_on",
            {"_config": {"url": "http://device.local/api", "method": "POST"}},
        )

        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
