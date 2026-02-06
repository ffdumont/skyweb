"""LLM-powered NOTAM briefing service.

Generates human-readable briefings in French from technical NOTAMs
using Claude API.
"""

from __future__ import annotations

import os
import logging

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

BRIEFING_SYSTEM_PROMPT = """Tu es un assistant spécialisé dans le briefing de vol VFR pour pilotes privés français.

Ta mission est de transformer les NOTAMs techniques en un briefing clair et concis en français.

Règles:
- Utilise un langage clair et direct, adapté aux pilotes VFR
- Mets en avant les informations critiques pour la sécurité du vol
- Organise les informations par ordre d'importance
- Traduis les abréviations OACI en français quand c'est utile
- Indique les dates/heures en heure locale française (UTC+1 ou UTC+2 selon l'heure d'été)
- Sois concis mais complet
- Si un NOTAM concerne une restriction d'espace aérien (zone D, R, P), mets-le en évidence
- Signale les NOTAMs qui pourraient impacter le déroulement du vol

Format de sortie:
- Commence par un résumé en 2-3 phrases
- Puis détaille par catégorie si nécessaire
- Termine par les points d'attention particuliers
"""


def _clean_text(text: str) -> str:
    """Remove BOM and other problematic characters from text."""
    if not text:
        return ""
    # Remove BOM (Byte Order Mark) and other zero-width characters
    return text.replace('\ufeff', '').replace('\ufffe', '').strip()


def format_notams_for_briefing(
    departure_icao: str,
    destination_icao: str,
    departure_notams: list[dict],
    destination_notams: list[dict],
    fir_notams: list[dict],
    enroute_notams: list[dict],
    flight_date: str | None = None,
) -> str:
    """Format NOTAMs into a structured text for LLM input."""
    lines = []

    lines.append(f"VOL: {departure_icao} -> {destination_icao}")
    if flight_date:
        lines.append(f"DATE DU VOL: {flight_date}")
    lines.append("")

    if departure_notams:
        lines.append(f"=== NOTAMS DEPART ({departure_icao}) ===")
        for n in departure_notams:
            msg = _clean_text(n.get('message', n.get('raw', '')))
            lines.append(f"[{n.get('id', 'N/A')}] {msg}")
        lines.append("")

    if destination_notams:
        lines.append(f"=== NOTAMS DESTINATION ({destination_icao}) ===")
        for n in destination_notams:
            msg = _clean_text(n.get('message', n.get('raw', '')))
            lines.append(f"[{n.get('id', 'N/A')}] {msg}")
        lines.append("")

    if fir_notams:
        lines.append("=== NOTAMS FIR ===")
        for n in fir_notams:
            msg = _clean_text(n.get('message', n.get('raw', '')))
            lines.append(f"[{n.get('id', 'N/A')}] {msg}")
        lines.append("")

    if enroute_notams:
        lines.append("=== NOTAMS EN-ROUTE ===")
        for n in enroute_notams:
            msg = _clean_text(n.get('message', n.get('raw', '')))
            lines.append(f"[{n.get('id', 'N/A')}] {msg}")
        lines.append("")

    if not any([departure_notams, destination_notams, fir_notams, enroute_notams]):
        lines.append("Aucun NOTAM significatif pour ce vol.")

    return "\n".join(lines)


class BriefingService:
    """Service for generating NOTAM briefings using Claude API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        self._client = None

    def _get_client(self):
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("No Anthropic API key configured")
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
        return self._client

    def generate_briefing(
        self,
        departure_icao: str,
        destination_icao: str,
        departure_notams: list[dict],
        destination_notams: list[dict],
        fir_notams: list[dict],
        enroute_notams: list[dict],
        flight_date: str | None = None,
    ) -> str:
        """Generate a briefing from NOTAMs using Claude.

        Args:
            departure_icao: Departure airport ICAO code
            destination_icao: Destination airport ICAO code
            departure_notams: NOTAMs for departure airport
            destination_notams: NOTAMs for destination airport
            fir_notams: NOTAMs for FIRs crossed
            enroute_notams: NOTAMs along the route
            flight_date: Optional flight date for context

        Returns:
            Human-readable briefing in French
        """
        client = self._get_client()

        # Format NOTAMs for input
        notam_text = format_notams_for_briefing(
            departure_icao=departure_icao,
            destination_icao=destination_icao,
            departure_notams=departure_notams,
            destination_notams=destination_notams,
            fir_notams=fir_notams,
            enroute_notams=enroute_notams,
            flight_date=flight_date,
        )

        total_notams = len(departure_notams) + len(destination_notams) + len(fir_notams) + len(enroute_notams)

        if total_notams == 0:
            return "Aucun NOTAM significatif pour ce vol. Conditions nominales."

        logger.info(f"Generating briefing for {departure_icao}->{destination_icao} with {total_notams} NOTAMs")

        try:
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                system=BRIEFING_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"Génère un briefing NOTAM en français pour ce vol:\n\n{notam_text}"
                    }
                ]
            )

            briefing = message.content[0].text
            logger.info(f"Briefing generated successfully ({len(briefing)} chars)")
            return briefing

        except Exception as e:
            logger.error(f"Failed to generate briefing: {e}")
            raise
