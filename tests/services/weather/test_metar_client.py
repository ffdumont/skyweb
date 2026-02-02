"""Tests for METAR client with mocked HTTP responses."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from core.contracts.enums import CloudCover
from core.services.weather.metar_client import MetarClient

SAMPLE_METAR = {
    "icaoId": "LFPG",
    "reportTime": "2025-06-15T08:30:00Z",
    "temp": 18.0,
    "dewp": 12.0,
    "wdir": 270,
    "wspd": 10.0,
    "wgst": None,
    "visib": 6.2,  # statute miles
    "altim": 1015.0,
    "fltcat": "VFR",
    "clouds": [
        {"cover": "FEW", "base": 3000},
        {"cover": "SCT", "base": 5000},
    ],
    "rawOb": "METAR LFPG 150830Z 27010KT 9999 FEW030 SCT050 18/12 Q1015",
}


class TestMetarClient:
    async def test_get_current_metar(self):
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=[SAMPLE_METAR])
        )
        async with httpx.AsyncClient(transport=transport) as http:
            client = MetarClient(http_client=http)
            obs = await client.get_current_metar("LFPG")
            assert obs is not None
            assert obs.icao == "LFPG"
            assert obs.temperature == 18.0
            assert obs.wind_direction == 270
            assert obs.wind_speed == 10.0
            assert obs.flight_category == "VFR"
            assert len(obs.clouds) == 2
            assert obs.clouds[0].cover == CloudCover.FEW
            assert obs.clouds[0].base_ft == 3000

    async def test_visibility_converted_to_meters(self):
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=[SAMPLE_METAR])
        )
        async with httpx.AsyncClient(transport=transport) as http:
            client = MetarClient(http_client=http)
            obs = await client.get_current_metar("LFPG")
            assert obs is not None
            # 6.2 SM * 1609.34 ≈ 9977 meters
            assert obs.visibility is not None
            assert 9900 < obs.visibility < 10100

    async def test_no_metar_returns_none(self):
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=[])
        )
        async with httpx.AsyncClient(transport=transport) as http:
            client = MetarClient(http_client=http)
            obs = await client.get_current_metar("ZZZZ")
            assert obs is None

    async def test_ceiling_from_bkn_layer(self):
        metar_with_bkn = {
            **SAMPLE_METAR,
            "clouds": [
                {"cover": "FEW", "base": 2000},
                {"cover": "BKN", "base": 4000},
                {"cover": "OVC", "base": 6000},
            ],
        }
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=[metar_with_bkn])
        )
        async with httpx.AsyncClient(transport=transport) as http:
            client = MetarClient(http_client=http)
            obs = await client.get_current_metar("LFPG")
            assert obs is not None
            assert obs.ceiling == 4000  # Lowest BKN

    async def test_get_metar_at_time(self):
        """get_metar_at_time should return closest observation."""
        metars = [
            {**SAMPLE_METAR, "reportTime": "2025-06-15T07:30:00Z"},
            {**SAMPLE_METAR, "reportTime": "2025-06-15T08:30:00Z"},
            {**SAMPLE_METAR, "reportTime": "2025-06-15T09:30:00Z"},
        ]
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=metars)
        )
        async with httpx.AsyncClient(transport=transport) as http:
            client = MetarClient(http_client=http)
            target = datetime(2025, 6, 15, 8, 45, tzinfo=timezone.utc)
            obs = await client.get_metar_at_time("LFPG", target)
            assert obs is not None
            # Closest to 08:45 is 08:30
            assert obs.observation_time.hour == 8
            assert obs.observation_time.minute == 30
