# Integration with Spoolman_ext for filament datas
#
# Copyright (C) 2023 fbeaukmi@mail.eu
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    from typing import Optional
    from moonraker.websockets import WebRequest
    from moonraker.components.http_client import HttpClient
    from .klippy_apis import KlippyAPI as APIComp
    from .spoolman import SpoolManager as SMan
    from confighelper import ConfigHelper
    from tornado.websocket import WebSocketClientConnection


class SpoolManager_ext:
    def __init__(self, config: ConfigHelper):
        self.server = config.get_server()
        self.gcode = config.gettemplate("gcode")

        self.klippy_apis: APIComp = self.server.lookup_component("klippy_apis")
        self.http_client: HttpClient = self.server.lookup_component("http_client")

        self.server.register_remote_method(
            "get_spoolman_datas", self.return_spool_datas
        )
        self.server.register_event_handler(
            "server:klippy_ready", self._handle_server_ready
        )
        self.server.register_event_handler(
            "spoolman:active_spool_set", self._handle_active_spool_set
        )

    async def _handle_server_ready(self) -> None:
        self.spoolman: SMan = self.server.lookup_component("spoolman")

    async def _handle_active_spool_set(self, _) -> None:
        eventloop = self.server.get_event_loop()
        eventloop.delay_callback(0.05, self.return_spool_datas)

    async def return_spool_datas(self) -> None:
        ws_connected: bool = self.spoolman.ws_connected
        spool_id = self.spoolman.spool_id

        spool_datas = "{}"

        if ws_connected:
            if spool_id is not None:
                response = await self.http_client.request(
                    method="GET",
                    url=f"{self.spoolman.spoolman_url}/v1/spool/{spool_id}",
                )
                if not response.has_error():
                    spool_datas = response.json()
                else:
                    spool_datas = {"id": 0}

            gcommands = self.gcode.render({"spool": spool_datas})
            for gcommand in gcommands.split("\n"):
                try:
                    await self.klippy_apis.run_gcode(gcommand)
                    logging.info("Sending Gcode to Klipper")
                except self.server.error:
                    msg = f"Error executing GCode {gcommand}"
                    logging.exception(msg)

        else:
            msg = "Unable to connect Spoolman server"
            logging.exception(msg)


def load_component(config: ConfigHelper) -> SpoolManager_ext:
    return SpoolManager_ext(config)
