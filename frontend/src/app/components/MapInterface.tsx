"use client";

import React, { useState, useEffect, useRef, useMemo } from 'react';
import Map, { Source, Layer, NavigationControl, Popup, MapRef, type LayerProps } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { MapLayerMouseEvent } from 'maplibre-gl';
import { useDistrictMetrics } from '../hooks/useDistrictMetrics';
import type { DistrictMetric } from '../services/api/types';

interface MapInterfaceProps {
    year: number;
    crop?: string;
    metric?: string;
    selectedDistrict?: string | null;
    onDistrictSelect: (id: string) => void;
    showRainfallLayer?: boolean;
}

import { getAgriColor, getRainfallColor } from '../utils/colors';
import { MapLegend } from './MapLegend';



export default function MapInterface({ year, crop = 'wheat', metric = 'yield', selectedDistrict, onDistrictSelect, showRainfallLayer = false }: MapInterfaceProps) {
    const mapRef = useRef<MapRef>(null);
    const [viewState, setViewState] = useState({
        longitude: 78.9629,
        latitude: 20.5937,
        zoom: 4
    });

    // Data Hook (The V1.5 Pipeline)
    const { joinedData, loading } = useDistrictMetrics(year, crop, metric);

    // Compute Style Layer
    const { layerStyle, min, max } = useMemo(() => {
        if (loading || Object.keys(joinedData).length === 0) {
            return {
                layerStyle: {
                    id: 'district-data',
                    type: 'fill',
                    paint: { 'fill-color': '#374151', 'fill-opacity': 0.6 }
                },
                min: 0,
                max: 0
            };
        }

        // Calculate Min/Max for scaling
        const values = Object.values(joinedData).map(d => d.value).filter(v => v > 0);
        const minVal = Math.min(...values);
        const maxVal = Math.max(...values);

        // Construct Match Expression
        // Use coalesce to handle variant property names in GeoJSON
        const districtExpr = ['coalesce', ['get', 'DISTRICT'], ['get', 'district_name']];
        const stateExpr = ['coalesce', ['get', 'STATE'], ['get', 'ST_NM']];
        const keyExpr = ['concat', districtExpr, '|', stateExpr];

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const matchExpr: any[] = ['match', keyExpr];

        // Use different color schemes based on layer mode
        const colorFn = showRainfallLayer ? getRainfallColor : getAgriColor;

        Object.entries(joinedData).forEach(([geoKey, d]) => {
            matchExpr.push(geoKey);
            matchExpr.push(colorFn(d.value, minVal, maxVal));
        });

        matchExpr.push('#374151'); // Default color (gray-700)

        return {
            layerStyle: {
                id: 'district-data',
                type: 'fill',
                paint: {
                    'fill-color': matchExpr,
                    'fill-opacity': 0.7,
                    'fill-outline-color': '#000000'
                }
            },
            min: minVal,
            max: maxVal
        };

    }, [joinedData, loading, showRainfallLayer]);

    // Fly to selection
    useEffect(() => {
        // ... (Coordinate logic omitted for brevity in V1 POC)
    }, [selectedDistrict]);

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [hoverInfo, setHoverInfo] = useState<{ feature: any, x: number, y: number, lngLat?: any, data?: DistrictMetric } | null>(null);

    const onHover = React.useCallback((event: MapLayerMouseEvent) => {
        const { features, point: { x, y } } = event;

        const feature = features && features[0];

        if (feature) {
            const dist = feature.properties?.DISTRICT;
            const state = feature.properties?.STATE;
            const geoKey = `${dist}|${state}`;
            const metricData = joinedData[geoKey];

            setHoverInfo({
                feature: feature,
                x: x,
                y: y,
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                lngLat: event.lngLat as any,
                data: metricData
            });
        } else {
            setHoverInfo(null);
        }
    }, [joinedData]);

    const onClick = React.useCallback((event: MapLayerMouseEvent) => {
        const feature = event.features && event.features[0];
        if (feature) {
            // Pass back the display name
            onDistrictSelect(feature.properties?.DISTRICT || "unknown");
        }
    }, [onDistrictSelect]);

    return (
        <div className="w-full h-full relative group">
            <Map
                ref={mapRef}
                {...viewState}
                onMove={evt => setViewState(evt.viewState)}
                style={{ width: '100%', height: '100%' }}
                mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
                interactiveLayerIds={['district-data']}
                onMouseMove={onHover}
                onClick={onClick}
            >
                <NavigationControl position="top-right" />

                <Source type="geojson" data="/data/districts.json">
                    {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                    <Layer {...(layerStyle as any)} />
                    <Layer id="borders" type="line" paint={{ 'line-color': '#ffffff', 'line-width': 0.5, 'line-opacity': 0.2 }} />
                    {/* Dashed borders for harmonized (backcast) districts — boundary uncertainty */}
                    <Layer {...({
                        id: 'harmonized-borders',
                        type: 'line',
                        paint: {
                            'line-color': '#fbbf24',
                            'line-width': (() => {
                                const districtExpr = ['coalesce', ['get', 'DISTRICT'], ['get', 'district_name']];
                                const stateExpr = ['coalesce', ['get', 'STATE'], ['get', 'ST_NM']];
                                const keyExpr = ['concat', districtExpr, '|', stateExpr];
                                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                const matchExpr: any[] = ['match', keyExpr];
                                let hasHarmonized = false;
                                Object.entries(joinedData).forEach(([geoKey, d]) => {
                                    if (d.method && d.method !== 'Raw') {
                                        matchExpr.push(geoKey);
                                        matchExpr.push(1.5);
                                        hasHarmonized = true;
                                    }
                                });
                                if (!hasHarmonized) return 0;
                                matchExpr.push(0); // default: no border for raw
                                return matchExpr;
                            })(),
                            'line-opacity': 0.7,
                            'line-dasharray': [2, 2],
                        }
                    } as LayerProps)} />
                </Source>

                {hoverInfo && hoverInfo.lngLat && (
                    <Popup
                        longitude={hoverInfo.lngLat.lng}
                        latitude={hoverInfo.lngLat.lat}
                        offset={[0, -10]}
                        closeButton={false}
                        className="text-black"
                    >
                        <div className="p-2">
                            <h3 className="font-bold text-lg">{hoverInfo.feature.properties?.DISTRICT}</h3>
                            <p className="text-sm text-gray-500">{hoverInfo.feature.properties?.STATE}</p>

                            <hr className="my-2 border-gray-200" />

                            {hoverInfo.data ? (
                                <div>
                                    <div className="flex justify-between items-center gap-4">
                                        <span className="capitalize text-gray-700 font-medium">{crop} {metric}</span>
                                        <span className="font-bold text-blue-600 text-lg">
                                            {hoverInfo.data.value.toLocaleString()}
                                            <span className="text-xs text-gray-500 ml-1">
                                                {metric === 'yield' ? 'kg/ha' : metric === 'production' ? 'tons' : 'ha'}
                                            </span>
                                        </span>
                                    </div>
                                    <div className="mt-1 text-xs text-gray-400">
                                        Source: {hoverInfo.data.method === 'Raw' ? 'Observed' : 'Harmonized (Backcast)'}
                                    </div>
                                </div>
                            ) : (
                                <p className="text-xs text-red-400 italic">No Data Available</p>
                            )}
                        </div>
                    </Popup>
                )}
            </Map>

            {/* Legend */}
            {!loading && min > 0 && (
                <MapLegend
                    min={min}
                    max={max}
                    label={showRainfallLayer ? "Rainfall (mm)" : `${crop} ${metric}`}
                    type={showRainfallLayer ? 'rainfall' : 'agri'}
                />
            )}

            {/* Loading Indicator */}
            {loading && (
                <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-slate-900/80 text-white px-6 py-3 rounded-full text-sm backdrop-blur border border-slate-700 shadow-2xl flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
                    <span>Processing Historical Geometries...</span>
                </div>
            )}
        </div>
    );
}
