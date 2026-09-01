# Integration with Spoolman_ext for filament datas
#
# Copyright (C) 2023-2026 fbeaukmi@mail.eu
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from __future__ import annotations

import base64
import json
import logging
import zlib
from typing import TYPE_CHECKING, Any

from ..common import RequestType
from ..utils import Sentinel

if TYPE_CHECKING:

    from confighelper import ConfigHelper
    from moonraker.components.http_client import HttpClient

    from .klippy_apis import KlippyAPI as APIComp
    from .spoolman import SpoolManager as SMan

logger = logging.getLogger(__name__)


class Kbobine:
    def __init__(self, config: ConfigHelper):
        self.server = config.get_server()
        self.hostname = self.server.get_host_info()["hostname"]
        self.level = config.getchoice(
            "level", ["spool", "filament"], default_key="filament"
        )
        self.compress = config.getboolean("compressed_datas", default=True)

        self.klippy_apis: APIComp = self.server.lookup_component("klippy_apis")
        self.http_client: HttpClient = self.server.lookup_component("http_client")

        # Initialize component variables
        self.sp: SMan | None = None
        self.last_spool_id: int = 0

        self._error_logged = False
        self.spoolman_datas: dict[
            str, Any
        ] = {}  # Datas received from Spoolman, unformatted and unfiltered
        self.kbobine_datas: dict[
            str, Any
        ] = {}  # Datas to send to Klipper, filtered and formatted from Spoolman datas

        self._register_remote_methods()
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.server.register_event_handler(
            "server:klippy_ready", self._handle_server_ready
        )
        self.server.register_event_handler(
            "spoolman:active_spool_set", self._handle_active_spool_set
        )

    def _register_remote_methods(self) -> None:
        self.server.register_remote_method(
            "get_spoolman_datas", self.return_spool_datas
        )
        self.server.register_remote_method("set_spoolman_datas", self.set_datas)

    async def _handle_server_ready(self) -> None:
        try:
            self.sp: SMan = self.server.lookup_component("spoolman")
        except (LookupError, AttributeError):
            logger.info(
                "Spoolman component not available, kbobine Moonraker extension unable to start"
            )
            return
        await self.get_spool_datas(0)

    async def _handle_active_spool_set(self, _) -> None:
        eventloop = self.server.get_event_loop()
        eventloop.delay_callback(0.1, self.return_spool_datas)

    # Get spoolman datas, filter and format them, then send them to Klipper
    async def return_spool_datas(self) -> None:
        result = await self.get_spool_datas(0)
        if not result:
            logger.info("Failed to get spoolman datas")
            message = "Failed to get spoolman datas"
            await self._respond_klipper(
                caller_id="get_spoolman_datas",
                messagetype="error",
                message=message,
            )

        try:
            logger.info("Sending Spoolman datas to Klipper: %s", self.kbobine_datas)
            result = await self.klippy_apis._send_klippy_request(
                "kbobine/set_spool", params={"spoolman": self.kbobine_datas}
            )
            logger.info("Klipper response: %s", result)
        except (
            AttributeError,
            ConnectionError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as err:
            logger.info(
                "Unable to join kbobine/set_spool endpoint, make sure kbobine is properly installed in Klipper: %s",
                err,
            )

    async def _respond_klipper(
        self, caller_id: str, messagetype: str = "message", message: str = ""
    ) -> None:
        try:
            result = await self.klippy_apis._send_klippy_request(
                "kbobine/response",
                params={"caller_id": caller_id, "response": {messagetype: message}},
            )
            logger.info("Klipper response: %s", result)
        except (
            AttributeError,
            ConnectionError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as err:
            logger.info(
                "Unable to join kbobine/response endpoint: %s",
                err,
            )

    # Get spoolman datas and filter them to keep only relevant parameters for Klipper, then store them in self.kbobine_datas
    async def get_spool_datas(self, eventtime: float) -> bool:
        if not self.sp.ws_connected:
            return False
        if self.last_spool_id == self.sp.spool_id:
            return True
        spool_id = self.sp.spool_id
        self.last_spool_id = spool_id
        self.spoolman = {}
        self.kbobine_datas = {
            "spool_id": 0
        }  # Initialize with default spool_id 0, which means no active spool.
        if spool_id is not None:
            logger.info(f"Requesting spool info for ID: {spool_id}")
            response = await self.http_client.request(
                method="GET",
                url=f"{self.sp.spoolman_url}/v1/spool/{spool_id}",
            )
            if response.has_error():
                if not self._error_logged:
                    error_msg = self.sp._get_response_error(response)
                    self._error_logged = True
                    message = (
                        f"Failed to get datas for spool id {spool_id}, "
                        f"received {error_msg}"
                    )
                    logger.info(message)
                self.last_spool_id = 0
                return False
            self._error_logged = False
            try:
                self.spoolman_datas = response.json()
                self.kbobine_datas = self.filter_spoolman_datas(self.spoolman_datas)
                logger.info(f"Successfully {self.spoolman_datas}")
            except (ValueError, TypeError) as err:
                self.last_spool_id = 0
                logger.info(
                    f"Error parsing spoolman response for spool id {spool_id}: {err}"
                )
        return True

    # Set kbobine datas in Spoolman extra fields, after filtering and formatting them, only if they have changed compared to current stored datas.
    async def set_datas(self, spoolman_datas: dict[str, Any]) -> None:

        result = await self.get_spool_datas(0)
        if not result:
            await self._respond_klipper(
                caller_id="set_spoolman_datas",
                messagetype="error",
                message="Spoolman Server unreachable",
            )
            return
        kbobine_datas = self.filter_kbobine_datas(spoolman_datas)

        if self.level == "spool":
            extra = self.spoolman_datas.get("extra", {})
            id = self.sp.spool_id
        elif self.level == "filament":
            extra = self.spoolman_datas.get("filament", {}).get("extra", {})
            id = self.spoolman_datas.get("filament", {}).get("id", 0)

        if extra.get("kbobine") != kbobine_datas:
            extra["kbobine"] = f'"{kbobine_datas}"'
            logger.info(f"Send extra datas: {extra}")
            result = await self.http_client.request(
                method="PATCH",
                url=f"{self.sp.spoolman_url}/v1/{self.level}/{id}",
                body={"extra": extra},
            )
            if result.has_error():
                error_msg = self.sp._get_response_error(result)
                message = f"Failed to update Spoolman server for {self.level} id {id}, received {error_msg}"
                await self._respond_klipper(
                    caller_id="set_spoolman_datas", messagetype="error", message=message
                )
                logger.info(message)
            else:
                message = f"Spoolman database successfully updated : {self.level} #{self.sp.spool_id}"
                logger.info(message)
        else:
            logger.info("No kbobine data to set")

        return

    # Filter and format spoolman datas to keep only relevant parameters for Klipper, then store them in self.kbobine_datas
    def filter_spoolman_datas(self, spoolman_datas: dict[str, Any]) -> dict[str, Any]:
        """Filter spoolman datas to keep only parameters needed"""
        if self.level == "spool":
            level_datas = spoolman_datas
        elif self.level == "filament":
            level_datas = spoolman_datas["filament"]
        try:
            kbobine_datas = self.decompress_extra_datas(level_datas["extra"]["kbobine"])
        except (KeyError, TypeError):
            kbobine_datas = {}

        try:
            datas = {
                "spool_id": spoolman_datas.get("id"),
                "filament": spoolman_datas.get("filament", {}).get("name"),
                "vendor": spoolman_datas.get("filament", {})
                .get("vendor", {})
                .get("name"),
                "color": spoolman_datas.get("filament", {}).get("color_hex"),
                "material": spoolman_datas.get("filament", {}).get("material"),
                "kbobine": kbobine_datas,
            }
        except (AttributeError, TypeError, ValueError):
            logger.info("Error parsing spoolman datas: %s", spoolman_datas)
            return kbobine_datas
        return datas

    def filter_kbobine_datas(self, kbobine_datas: dict[str, Any]) -> dict[str, Any]:
        """Filter kbobine datas to keep only parameters needed for spoolman extrafields"""
        self.kbobine_datas.setdefault("kbobine", {}).update(
            {self.hostname: kbobine_datas}
        )
        try:
            datas = self.compress_extra_datas(self.kbobine_datas["kbobine"])
        except (TypeError, ValueError):
            logger.info("Error parsing kbobine datas: %s", kbobine_datas)
            return {}
        return datas

    def decompress_extra_datas(self, base64_encoded_data: str) -> dict[str, Any]:
        """Try read as uncompressed datas then decompress extra datas stored in spoolman extra"""
        try:
            json_data = json.loads(base64_encoded_data[1:-1].replace('\\"', '"'))
            if isinstance(json_data, dict):
                return json_data
        except (json.JSONDecodeError, TypeError, IndexError):
            pass

        try:
            decoded_data = base64.b64decode(base64_encoded_data)
            decompressed_data = zlib.decompress(decoded_data)
            return json.loads(decompressed_data.decode("utf-8"))
        except (zlib.error, json.JSONDecodeError, UnicodeDecodeError, TypeError):
            logger.info("Error reading extra datas: %s", base64_encoded_data)
            return {}

    def compress_extra_datas(self, data: dict[str, Any]) -> str:
        """Compress extra datas to store in spoolman extra"""

        uncompressed_data = json.dumps(data).replace('"', '\\"')
        if not self.compress:
            logger.info("Compression disabled, storing datas without compression")
            return uncompressed_data

        json_data = json.dumps(data).encode("utf-8")
        compressed_data = zlib.compress(json_data)
        base64_encoded_data = base64.b64encode(compressed_data).decode("utf-8")
        return (
            base64_encoded_data
            if len(base64_encoded_data) < len(uncompressed_data)
            else uncompressed_data
        )


def load_component(config: ConfigHelper) -> Kbobine:
    return Kbobine(config)
