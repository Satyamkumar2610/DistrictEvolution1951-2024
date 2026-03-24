import React, { useEffect } from 'react';
import { Source, Layer, useMap } from 'react-map-gl/maplibre';
import * as turf from '@turf/turf';

export default function ReconstructedMapLayer({ epoch }: { epoch: any }) {
    const { current: map } = useMap();

    useEffect(() => {
        if (map && epoch?.reconstructed_geojson) {
            try {
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
    }, [map, epoch?.reconstructed_geojson]);

    if (!epoch || !epoch.reconstructed_geojson) return null;

    const isVirtual = epoch.is_virtual;
    const latestYield = epoch.metrics && epoch.metrics.length > 0 
        ? epoch.metrics[epoch.metrics.length - 1].collective_yield 
        : null;

    // Dynamic gradient color based on yield
    let fillColor = "#475569"; // default slate-600
    if (isVirtual) {
        fillColor = "#6366f1"; // indigo for virtual
    } else if (latestYield) {
        if (latestYield < 1000) fillColor = "#e11d48"; // rose-600
        else if (latestYield < 1500) fillColor = "#f59e0b"; // amber-500
        else if (latestYield < 2000) fillColor = "#eab308"; // yellow-500
        else if (latestYield < 2500) fillColor = "#84cc16"; // lime-500
        else if (latestYield < 3000) fillColor = "#22c55e"; // green-500
        else if (latestYield < 3500) fillColor = "#10b981"; // emerald-500
        else fillColor = "#06b6d4"; // cyan-500
    }

    const fillOpacity = isVirtual ? 0.15 : 0.35;
    const lineColor = isVirtual ? "#818cf8" : "#e2e8f0";
    const lineWidth = isVirtual ? 1.5 : 2;

    return (
        <Source id="reconstructed" type="geojson" data={epoch.reconstructed_geojson}>
            <Layer 
                id="reconstructed-fill" 
                type="fill" 
                paint={{ 
                    "fill-color": fillColor, 
                    "fill-opacity": fillOpacity,
                }} 
            />
            <Layer 
                id="reconstructed-line" 
                type="line" 
                paint={{ 
                    "line-color": lineColor, 
                    "line-width": lineWidth,
                    "line-opacity": 0.8,
                    ...(isVirtual ? { "line-dasharray": [4, 3] as any } : {}),
                }} 
            />
            {/* Glow effect for boundaries */}
            <Layer 
                id="reconstructed-glow" 
                type="line" 
                paint={{ 
                    "line-color": isVirtual ? "#6366f1" : fillColor, 
                    "line-width": 6,
                    "line-opacity": 0.15,
                    "line-blur": 4,
                }} 
            />
        </Source>
    );
}
