"""Supporting API for Daikin Cloud NA."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, fields
import json
import logging
from typing import Optional
from typing import Any

import aiohttp
from dataclasses_json import dataclass_json
import socketio

# from .daikincloud import DaikinInstallation

logger = logging.getLogger("DaikinCloud")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.NOTSET)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)
logger.debug("Logger Initialized")
logging.basicConfig(level=logging.NOTSET)

private_engineio_logger = logging.getLogger("engineio.client")
private_engineio_logger.setLevel(logging.ERROR)


@dataclass_json
@dataclass
class DeviceManufacturer:
    _id: Optional[int] = None
    text: Optional[str] = None


@dataclass_json
@dataclass
class DeviceData:
    machineready: Optional[bool] = None
    version: Optional[str] = None
    aidooit: Optional[bool] = None
    emerheatpresent: Optional[bool] = None
    emerheatstatus: Optional[bool] = None
    fallback: Optional[bool] = None
    t1t2on: Optional[bool] = None
    real_mode: Optional[int] = None
    work_temp_selec_sensor: Optional[int] = None
    stat_channel: Optional[int] = None
    stat_rssi: Optional[int] = None
    stat_ssid: Optional[str] = None
    manufacturer: Optional[DeviceManufacturer] = None
    power: Optional[bool] = None
    mode: Optional[int] = None
    mode_available: Optional[Any] = None
    speed_available: Optional[Any] = None
    speed_state: Optional[int] = None
    slats_autoud: Optional[bool] = None
    slats_swingud: Optional[bool] = None
    slats_vnum: Optional[int] = None
    range_sp_cool_air_max: Optional[int] = None
    range_sp_cool_air_min: Optional[int] = None
    range_sp_hot_air_max: Optional[int] = None
    range_sp_hot_air_min: Optional[int] = None
    range_sp_auto_air_max: Optional[int] = None
    range_sp_auto_air_min: Optional[int] = None
    device_master_slave: Optional[bool] = None
    master: Optional[bool] = None
    setpoint_step: Optional[bool] = None
    units: Optional[int] = None
    setpoint_air_cool: Optional[int] = None
    setpoint_air_heat: Optional[int] = None
    setpoint_air_auto: Optional[int] = None
    error_value: Optional[int] = None
    error_ascii1: Optional[str] = None
    error_ascii2: Optional[str] = None
    tsensor_error: Optional[bool] = None
    work_temp: Optional[int] = None
    icon: Optional[int] = None
    name: Optional[str] = None
    timezoneId: Optional[str] = None
    isConnected: Optional[bool] = None


@dataclass_json
@dataclass
class DeviceDataMessage:
    """Template."""

    mac: Optional[str] = None
    data: Optional[DeviceData] = None


class DaikinCloudClient:
    """Template."""

    API_URL: str = "https://dkncloudna.com/"
    API_VER: str = "api/v1"
    SCOPE: str = "dknUsa"
    SOCKET_PATH: str = "api/v1/devices/socket.io/"
    access_token: str = ""
    refresh_token: str = ""
    user_name: str = ""
    user_pass: str = ""
    full_login_info: dict = {}
    full_installation_info: dict = {}

    async def authenticate(self, user: str, passw: str):
        """Template."""
        async with aiohttp.ClientSession() as session:
            body = {"email": user, "password": passw}
            url = f"{self.API_URL}{self.API_VER}/auth/login/{self.SCOPE}"
            async with session.post(url, json=body) as response:
                resp_json = await response.json()
                self.full_login_info = resp_json
                self.access_token = resp_json["token"]
                self.refresh_token = resp_json["refreshToken"]
        await self.load_installations()

    async def load_installations(self):
        """Template."""
        async with aiohttp.ClientSession() as session:
            url = f"{self.API_URL}{self.API_VER}/installations/{self.SCOPE}"
            headers = {}
            headers["Access-Control-Allow-Origin"] = "*"
            headers["Authorization"] = f"Bearer {self.access_token}"
            async with session.get(url, headers=headers) as resp:
                resp_json = await resp.json()
                self.full_installation_info = resp_json

    # def build_socket_url(self) -> str:
    #    """Template."""
    #    return f"{self.API_URL}{self.SOCKET_PATH}"

    def create_socket(self):
        """Template."""
        headers = {}
        headers["Authorization"] = f"Bearer {self.access_token}"
        session = aiohttp.ClientSession(headers=headers)
        socket = socketio.AsyncClient(
            http_session=session, engineio_logger=private_engineio_logger
        )
        return socket


class DaikinDevice:
    """Template."""

    full_json: dict = {}
    mac: str
    name: str
    data: DeviceData
    data_updated_callbacks: list[Callable]
    socket: socketio.AsyncClient
    namespace: str

    def __init__(self, d_json, _socket, _namespace):
        """Template."""
        self.full_json = d_json
        self.mac = d_json["mac"]
        self.name = d_json["name"]
        self.data = None
        self.data_updated_callbacks = []
        self.socket = _socket
        self.namespace = _namespace

    def handle_data(self, data: DeviceData):
        """Update this device model with new data from Daikin Cloud."""
        logger.debug("Got device Data for '%s'", self.name)

        if self.data is None:
            self.data = DeviceData()

        changes = False
        for field in fields(data):
            new_value = getattr(data, field.name)
            if new_value is not None:
                setattr(self.data, field.name, new_value)
                logger.debug(
                    "Device property '%s' changed to '%s'", field.name, new_value
                )
                changes = True
        if changes:
            # if self.data_updated_callbacks.__len__ > 0:
            self.notify_onupdate_listeners()

    async def wait_for_data(self):
        """Template."""
        while self.data is None:
            await asyncio.sleep(0.2)

    def register_on_update_callback(self, callback: Callable):
        """Template."""
        self.data_updated_callbacks.append(callback)
        try:
            callback()
        except Exception:
            logger.exception("Failed to execute a callback")

    def unregister_on_update_callback(self, callback: Callable):
        """Template."""
        self.data_updated_callbacks.remove(callback)

    def notify_onupdate_listeners(self):
        """Template."""
        for callback in self.data_updated_callbacks:
            try:
                callback()
            except Exception:
                logger.exception("Failed to execute a callback")

    async def emit(self, event, data, callback):
        """Proxies the Socket.IO emit but includes this installation's namespace."""
        await self.socket.emit(event, data, namespace=self.namespace, callback=callback)

    async def set_device_value(self, prop: str, value: str):
        """Sets a device value using the installation socket."""

        update_command = {"mac": self.mac, "property": prop, "value": value}

        def callback_fun(data):
            logger.debug(
                "(%s) POST - %s : %s; (raw: %s)",
                update_command["mac"],
                update_command["property"],
                update_command["value"],
                json.dumps(data),
            )

        logger.debug("Setting device '%s' value '%s' to '%s'", self.mac, prop, value)

        await self.emit("create-machine-event", update_command, callback=callback_fun)
        setattr(self.data, prop, value)


class DaikinInstallation:
    """Template."""

    full_json: dict = {}
    installation_id: str = ""
    installation_namespace: str = ""
    name: str = ""
    devices: dict[str, DaikinDevice] = {}
    socket: socketio.AsyncClient
    client: DaikinCloudClient

    def __init__(self, client: DaikinCloudClient, installation_json: dict) -> None:
        """Template."""
        self.client = client
        self.full_json = installation_json
        self.installation_id = installation_json["_id"]
        self.installation_namespace = f"/{self.installation_id}::{self.client.SCOPE}"
        self.name = installation_json["name"]
        self.socket = self.client.create_socket()

        for dev in installation_json["devices"]:
            self.devices[dev["mac"]] = DaikinDevice(
                dev, self.socket, self.installation_namespace
            )

    async def waif_for_data(self):
        """Template."""
        async with asyncio.TaskGroup() as tg:
            for dev in self.devices:
                tg.create_task(self.devices[dev].wait_for_data())

    async def connect_socket(self):
        """Template."""
        # self.socket = self.client.createSocket()
        await self.socket.connect(
            self.client.API_URL,
            transports=["polling"],
            namespaces=[self.installation_namespace],
            socketio_path=self.client.SOCKET_PATH,
        )

        @self.socket.on("*", namespace=self.installation_namespace)
        def catch_all_events(event, data):
            logger.debug(
                "Installation socket message '%s':'%s'",
                json.dumps(event),
                json.dumps(data),
            )

        @self.socket.on("device-data", namespace=self.installation_namespace)
        def on_device_data(data):
            logger.debug(
                "Device message: mac='%s' data='%s'",
                data["mac"],
                json.dumps(data["data"]),
            )
            device_data_message: DeviceDataMessage = DeviceDataMessage.from_dict(data)
            try:
                self.devices[device_data_message.mac].handle_data(
                    device_data_message.data
                )
            except KeyError:
                logger.warning(
                    "Device '%s' does not exist in installation '%s'",
                    device_data_message.mac,
                    self.installation_id,
                )

        @self.socket.event(namespace=self.installation_namespace)
        def message(data):
            logger.debug("Installation socket message '%s'", data)

        @self.socket.event
        def connect():
            """installation_socket Connect callback."""
            logger.debug(
                "Installation socket connected: '%s'",
                self.installation_namespace,
            )

        @self.socket.event
        def connect_error(data):
            """installation_socket Connect Error callback."""
            logger.debug("Installation socket connection failed!")

        @self.socket.event
        def disconnect():
            """installation_socket Disonnect callback."""
            logger.debug("Installation socketdisconnected!")


class DaikinCloud:
    """Template."""

    client: DaikinCloudClient = DaikinCloudClient()
    installations: dict[str, DaikinInstallation] = {}
    socket: socketio.AsyncClient
    # def __init__(self):

    async def login(self, user: str, passw: str):
        """Template."""
        await self.client.authenticate(user, passw)
        self.socket = self.client.create_socket()
        await self.connect_user_socket()

        for i in self.client.full_installation_info:
            new_installation = DaikinInstallation(self.client, i)
            self.installations[i["_id"]] = new_installation
            await new_installation.connect_socket()
            await new_installation.waif_for_data()

    async def connect_user_socket(self):
        """Template."""
        await self.socket.connect(
            self.client.API_URL,
            transports=["polling"],
            namespaces=["/users"],
            socketio_path=self.client.SOCKET_PATH,
        )

        @self.socket.on("*")
        def catch_all(event, data):
            """Default event handler."""
            logger.debug(
                "User socket message '%s': %s",
                json.dumps(event),
                json.dumps(data),
            )

        @self.socket.event(namespace="/users")
        def message(data):
            logger.debug("User socket event: '%s'", json.dumps(data))

        @self.socket.event(namespace="/users")
        def connect():
            """SIO Connect callback."""
            logger.debug("User socket connected!")

        @self.socket.event(namespace="/users")
        def connect_error(data):
            """SIO Connect Error callback."""
            logger.debug("User socket connection failed!")

        @self.socket.event(namespace="/users")
        def disconnect():
            """SIO Disonnect callback."""
            logger.debug("User socket disconnected!")
