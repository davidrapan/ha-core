"""Contains the Coordinator for updating the IP addresses of your Cloudflare DNS records."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from logging import getLogger
from typing import Self

import pycfdns

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_ZONE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_RECORDS, DEFAULT_UPDATE_INTERVAL
from .helpers import get_type_ip_map_from_location_info, list_dns_records

_LOGGER = getLogger(__name__)

type CloudflareConfigEntry = ConfigEntry[CloudflareCoordinator]


class CloudflareCoordinator(DataUpdateCoordinator[None]):
    """Coordinates records updates."""

    config_entry: CloudflareConfigEntry
    client: pycfdns.Client
    zone: pycfdns.ZoneModel

    def __init__(
        self, hass: HomeAssistant, config_entry: CloudflareConfigEntry
    ) -> None:
        """Initialize an coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL),
        )

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        self.client = pycfdns.Client(
            api_token=self.config_entry.data[CONF_API_TOKEN],
            client_session=async_get_clientsession(self.hass),
        )

        try:
            self.zone = next(
                zone
                for zone in await self.client.list_zones()
                if zone["name"] == self.config_entry.data[CONF_ZONE]
            )
        except pycfdns.AuthenticationException as e:
            raise ConfigEntryAuthFailed from e
        except pycfdns.ComunicationException as e:
            raise UpdateFailed("Error communicating with API") from e

    async def _async_update_data(self) -> None:
        """Update records."""
        _LOGGER.debug("Starting update for zone %s", self.zone["name"])
        try:
            records = await list_dns_records(self.client, self.zone["id"])
            _LOGGER.debug("Records: %s", records)

            target_records: list[str] = self.config_entry.data[CONF_RECORDS]
            type_ip = await get_type_ip_map_from_location_info(self.hass)
            if not type_ip:
                raise UpdateFailed("Could not get external IPv6 or IPv4 address")
            _LOGGER.debug("Record type to address map: %s", type_ip)

            filtered_records = [
                record
                for record in records
                if record["name"] in target_records
                and record["type"] in type_ip
                and record["content"] != type_ip[record["type"]]
            ]
            if not filtered_records:
                _LOGGER.debug("All records are up to date")
                return
            _LOGGER.debug("Records to update: %s", filtered_records)

            await asyncio.gather(
                *[
                    self.client.update_dns_record(
                        zone_id=self.zone["id"],
                        record_id=record["id"],
                        record_content=type_ip[record["type"]],
                        record_name=record["name"],
                        record_type=record["type"],
                        record_proxied=record["proxied"],
                    )
                    for record in filtered_records
                ]
            )

            _LOGGER.debug("Update for zone %s is complete", self.zone["name"])

        except (
            pycfdns.AuthenticationException,
            pycfdns.ComunicationException,
        ) as e:
            raise UpdateFailed(
                f"Error updating zone {self.config_entry.data[CONF_ZONE]}"
            ) from e

    async def init(self) -> Self:
        """Asynchronously initialize an coordinator."""
        await super().async_config_entry_first_refresh()

        @callback
        def _callback() -> None:
            """Records updated callback."""

        self.config_entry.async_on_unload(self.async_add_listener(_callback, None))

        return self
