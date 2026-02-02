"""CLI entry point for the ETL pipeline.

Usage:
    python -m core.etl.cli --xml-path /path/to/sia.xml --cycle 2604 --output /tmp/etl
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from core.etl.sia_parser import parse_sia_xml
from core.etl.spatialite_builder import SpatiaLiteBuilder
from core.etl.tile_generator import TileGenerator

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="SkyWeb ETL Pipeline")
    parser.add_argument("--xml-path", type=Path, required=True, help="Path to SIA XML file")
    parser.add_argument("--cycle", type=str, required=True, help="AIRAC cycle ID (e.g. 2604)")
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    parser.add_argument("--upload", action="store_true", help="Upload to GCS after building")
    parser.add_argument("--activate", action="store_true", help="Set as active cycle in GCS")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    args.output.mkdir(parents=True, exist_ok=True)

    # 1. Parse SIA XML
    logger.info("Parsing SIA XML: %s", args.xml_path)
    data = parse_sia_xml(args.xml_path)

    # 2. Build SpatiaLite DB
    db_path = args.output / f"skypath_{args.cycle}.db"
    logger.info("Building SpatiaLite DB: %s", db_path)
    builder = SpatiaLiteBuilder(db_path)
    builder.build(data)

    # 3. Generate tiles
    tiles_dir = args.output / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Generating tiles in: %s", tiles_dir)
    gen = TileGenerator(db_path, tiles_dir)
    tile_count = gen.generate_all()
    logger.info("Generated %d tiles", tile_count)

    # 4. Upload to GCS (optional)
    if args.upload:
        from core.etl.gcs_uploader import GCSUploader
        uploader = GCSUploader()
        summary = uploader.upload_cycle(args.cycle, db_path, tiles_dir)
        logger.info("Upload summary: %s", summary)

        if args.activate:
            uploader.set_active_cycle(args.cycle)
            logger.info("Activated cycle %s", args.cycle)

    logger.info("ETL pipeline complete for cycle %s", args.cycle)


if __name__ == "__main__":
    main()
