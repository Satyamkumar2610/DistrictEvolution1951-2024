import React, { useEffect } from 'react';
import { Source, Layer, useMap } from 'react-map-gl/maplibre';
import * as turf from '@turf/turf';

export default function ReconstructedMapLayer({ epoch }: { epoch: any }) {
    const { current: map } = useMap();
    if (!epoch || !epoch.reconstructed_geojson) return null;

    useEffect(() => {
        if (map && epoch.reconstructed_geojson) {
            try {
                // Ensure it's treated as a geometry or feature
                const geom = epoch.reconstructed_geojson.type === 'Feature' 
                    ? epoch.reconstructed_geojson 
                    : turf.feature(epoch.reconstructed_geojson);
                
                const bbox = turf.bbox(geom);
                map.fitBounds(
                    [[bbox[0], bbox[1]], [bbox[2], bbox[3]]],
                    { padding: 80, duration: 1200 }
                );
            } catch (err) {
                console.warn("Failed to fit bounds on reconstructed geom", err);
            }
        }
    }, [map, epoch.reconstructed_geojson]);

    const isVirtual = epoch.is_virtual;
    
    // Attempt to parse out some choropleth value 
    const latestYield = epoch.metrics && epoch.metrics.length > 0 
        ? epoch.metrics[epoch.metrics.length - 1].collective_yield 
        : null;

    // Simple fixed color scale mapping for India yields (e.g. 1000 to 4500 kg/ha)
    // If virtual or yield is null, neutral blue. Otherwise shade of green/indigo.
    let fillColor = "#cbd5e1"; // default null
    if (isVirtual) {
        fillColor = "#93c5fd"; // neutral blue
    } else if (latestYield) {
        if (latestYield < 1500) fillColor = "#c7d2fe"; // lowest
        else if (latestYield < 2500) fillColor = "#818cf8";
        else if (latestYield < 3500) fillColor = "#4f46e5";
        else fillColor = "#312e81"; // highest
    }

    const fillOpacity = isVirtual ? 0.2 : 0.45;
    const lineDasharray = isVirtual ? [4, 4] : [1];

    return (
        <Source id="reconstructed" type="geojson" data={epoch.reconstructed_geojson}>
            <Layer 
                id="reconstructed-fill" 
                type="fill" 
                paint={{ "fill-color": fillColor, "fill-opacity": fillOpacity }} 
            />
            <Layer 
                id="reconstructed-line" 
                type="line" 
                paint={{ 
                    "line-color": isVirtual ? "#2563eb" : "#1e1b4b", 
                    "line-width": 2,
                    ...(isVirtual ? { "line-dasharray": lineDasharray } : {})
                }} 
            />
        </Source>
    );
}
