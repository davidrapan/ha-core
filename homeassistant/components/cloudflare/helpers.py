"""Helpers for the CloudFlare integration."""

import asyncio
import socket

import pycfdns

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.location import async_detect_location_info
from homeassistant.util.network import is_ipv4_address, is_ipv6_address


def _get_type_from_ip(address: str) -> str | None:
    """Get record type based on IP address version."""
    if is_ipv6_address(address):
        return "AAAA"
    if is_ipv4_address(address):
        return "A"
    return None


def get_zone_id(target_zone_name: str, zones: list[pycfdns.ZoneModel]) -> str | None:
    """Get the zone ID for the target zone name."""
    for zone in zones:
        if zone["name"] == target_zone_name:
            return zone["id"]
    return None


async def list_dns_records(
    client: pycfdns.Client, zone_id: str
) -> list[pycfdns.RecordModel]:
    """List AAAA and A DNS records for given zone ID."""
    return [
        record
        for record in await client.list_dns_records(zone_id)
        if record["type"] in ("AAAA", "A")
    ]


async def get_type_ip_map_from_location_info(hass: HomeAssistant) -> dict[str, str]:
    """Get record type to IP address map from location info."""
    return {
        t: i.ip
        for i in (
            await asyncio.gather(
                async_detect_location_info(
                    async_get_clientsession(hass, family=socket.AF_INET6)
                ),
                async_detect_location_info(
                    async_get_clientsession(hass, family=socket.AF_INET)
                ),
            )
        )
        if i and (t := _get_type_from_ip(i.ip))
    }
