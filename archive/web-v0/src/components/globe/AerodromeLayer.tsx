import { useEffect, useState } from "react";
import { Entity, BillboardGraphics } from "resium";
import { Cartesian3, VerticalOrigin } from "cesium";
import { useMapStore } from "../../stores/mapStore";
import { getAerodromesBbox, type Aerodrome } from "../../api/aerodromes";

export default function AerodromeLayer() {
  const bounds = useMapStore((s) => s.bounds);
  const [aerodromes, setAerodromes] = useState<Aerodrome[]>([]);

  useEffect(() => {
    if (!bounds) return;
    let cancelled = false;

    getAerodromesBbox(bounds.south, bounds.west, bounds.north, bounds.east)
      .then((data) => {
        if (!cancelled) setAerodromes(data);
      })
      .catch(() => {
        // Ignore errors
      });

    return () => {
      cancelled = true;
    };
  }, [bounds]);

  return (
    <>
      {aerodromes.map((ad) => (
        <Entity
          key={ad.icao}
          name={ad.icao}
          description={`${ad.name} (${ad.icao})${ad.elevation_ft ? ` — ${ad.elevation_ft} ft` : ""}`}
          position={Cartesian3.fromDegrees(ad.longitude, ad.latitude)}
        >
          <BillboardGraphics
            image="/aerodrome-icon.svg"
            width={20}
            height={20}
            verticalOrigin={VerticalOrigin.CENTER}
          />
        </Entity>
      ))}
    </>
  );
}
