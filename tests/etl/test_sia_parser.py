"""Tests for SIA XML parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.etl.sia_parser import ParsedSIA, parse_sia_xml

# Minimal SIA XML fixture
MINIMAL_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<SIA>
  <Espace>
    <EspaceId>ESP001</EspaceId>
    <Nom>PARIS TMA 1</Nom>
    <TypeEspace>TMA</TypeEspace>
    <Classe>D</Classe>
  </Espace>
  <Espace>
    <EspaceId>ESP002</EspaceId>
    <Nom>BEAUVAIS CTR</Nom>
    <TypeEspace>CTR</TypeEspace>
    <Classe>D</Classe>
  </Espace>
  <Partie>
    <PartieId>P001</PartieId>
    <EspaceId>ESP001</EspaceId>
    <Nom>Partie 1</Nom>
  </Partie>
  <Volume>
    <VolumeId>V001</VolumeId>
    <PartieId>P001</PartieId>
    <Plancher>SFC</Plancher>
    <PlancherRef>AMSL</PlancherRef>
    <PlancherVal>0</PlancherVal>
    <Plafond>FL065</Plafond>
    <PlafondRef>STD</PlafondRef>
    <PlafondVal>6500</PlafondVal>
    <HorCode>H24</HorCode>
  </Volume>
  <Geometrie>
    <PartieId>P001</PartieId>
    <WKT>POLYGON((2.0 48.0, 2.5 48.0, 2.5 49.0, 2.0 49.0, 2.0 48.0))</WKT>
  </Geometrie>
  <Service>
    <IndicLieu>LFPG</IndicLieu>
    <Indicatif>PARIS Approche</Indicatif>
    <TypeService>APP</TypeService>
    <Langue>fr</Langue>
    <HorCode>H24</HorCode>
    <HorTxt>H24</HorTxt>
  </Service>
  <Frequence>
    <IndicLieu>LFPG</IndicLieu>
    <Frequence>119.250</Frequence>
    <Espacement>8.33</Espacement>
    <HorCode>H24</HorCode>
    <HorTxt>H24</HorTxt>
    <Secteur>Nord</Secteur>
    <Remarques></Remarques>
  </Frequence>
  <Ad>
    <AdCode>LFXU</AdCode>
    <AdNomComplet>LES MUREAUX</AdNomComplet>
    <AdStatut>CAP</AdStatut>
    <ArpLat>48.9897</ArpLat>
    <ArpLon>1.8815</ArpLon>
    <AdRefAltFt>164</AdRefAltFt>
  </Ad>
  <Rwy>
    <AdCode>LFXU</AdCode>
    <Identifiant>12/30</Identifiant>
    <Longueur>700</Longueur>
    <Largeur>30</Largeur>
    <Principal>1</Principal>
    <Revetement>Herbe</Revetement>
  </Rwy>
</SIA>
"""


@pytest.fixture
def xml_path(tmp_path: Path) -> Path:
    p = tmp_path / "test_sia.xml"
    p.write_text(MINIMAL_XML, encoding="utf-8")
    return p


class TestSIAParser:
    def test_parse_espaces(self, xml_path):
        data = parse_sia_xml(xml_path)
        assert len(data.espaces) == 2
        assert data.espaces[0]["Nom"] == "PARIS TMA 1"
        assert data.espaces[1]["TypeEspace"] == "CTR"

    def test_parse_parties(self, xml_path):
        data = parse_sia_xml(xml_path)
        assert len(data.parties) == 1
        assert data.parties[0]["Nom"] == "Partie 1"

    def test_parse_volumes(self, xml_path):
        data = parse_sia_xml(xml_path)
        assert len(data.volumes) == 1
        assert data.volumes[0]["PlafondVal"] == "6500"
        assert data.volumes[0]["HorCode"] == "H24"

    def test_parse_geometries(self, xml_path):
        data = parse_sia_xml(xml_path)
        assert len(data.geometries) == 1
        assert "POLYGON" in data.geometries[0]["WKT"]

    def test_parse_services(self, xml_path):
        data = parse_sia_xml(xml_path)
        assert len(data.services) == 1
        assert data.services[0]["Indicatif"] == "PARIS Approche"

    def test_parse_frequencies(self, xml_path):
        data = parse_sia_xml(xml_path)
        assert len(data.frequencies) == 1
        assert data.frequencies[0]["Frequence"] == "119.250"

    def test_parse_aerodromes(self, xml_path):
        data = parse_sia_xml(xml_path)
        assert len(data.aerodromes) == 1
        assert data.aerodromes[0]["AdCode"] == "LFXU"
        assert data.aerodromes[0]["ArpLat"] == "48.9897"

    def test_parse_runways(self, xml_path):
        data = parse_sia_xml(xml_path)
        assert len(data.runways) == 1
        assert data.runways[0]["Identifiant"] == "12/30"
        assert data.runways[0]["Longueur"] == "700"

    def test_returns_parsed_sia_type(self, xml_path):
        data = parse_sia_xml(xml_path)
        assert isinstance(data, ParsedSIA)
