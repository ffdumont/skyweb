"""SIA XML parser — extracts aeronautical data from data.gouv.fr XML exports."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ParsedSIA:
    """Complete parsed dataset from a SIA XML export."""

    espaces: list[dict] = field(default_factory=list)
    parties: list[dict] = field(default_factory=list)
    volumes: list[dict] = field(default_factory=list)
    geometries: list[dict] = field(default_factory=list)
    services: list[dict] = field(default_factory=list)
    frequencies: list[dict] = field(default_factory=list)
    aerodromes: list[dict] = field(default_factory=list)
    runways: list[dict] = field(default_factory=list)


def parse_sia_xml(xml_path: Path) -> ParsedSIA:
    """Parse all tables from a SIA XML export file.

    The SIA XML contains hierarchical records:
    - Espace → Partie → Volume → Geometrie
    - Service → Frequence (linked by IndicLieu)
    - Ad → Rwy (linked by AdCode)
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    result = ParsedSIA()

    for table in root:
        tag = _local_name(table.tag)
        row = _element_to_dict(table)

        if tag == "Espace":
            result.espaces.append(row)
        elif tag == "Partie":
            result.parties.append(row)
        elif tag == "Volume":
            result.volumes.append(row)
        elif tag == "Geometrie":
            result.geometries.append(row)
        elif tag == "Service":
            result.services.append(row)
        elif tag == "Frequence":
            result.frequencies.append(row)
        elif tag == "Ad":
            result.aerodromes.append(row)
        elif tag == "Rwy":
            result.runways.append(row)
        # Skip unknown tables silently

    logger.info(
        "Parsed SIA XML: %d espaces, %d parties, %d volumes, %d geometries, "
        "%d services, %d frequencies, %d aerodromes, %d runways",
        len(result.espaces),
        len(result.parties),
        len(result.volumes),
        len(result.geometries),
        len(result.services),
        len(result.frequencies),
        len(result.aerodromes),
        len(result.runways),
    )
    return result


def _local_name(tag: str) -> str:
    """Strip namespace prefix from an XML tag."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _element_to_dict(element: ET.Element) -> dict:
    """Convert an XML element and its children to a flat dict."""
    result: dict = {}
    for child in element:
        key = _local_name(child.tag)
        result[key] = (child.text or "").strip()
    # Also include attributes
    for attr_key, attr_val in element.attrib.items():
        result[_local_name(attr_key)] = attr_val
    return result
