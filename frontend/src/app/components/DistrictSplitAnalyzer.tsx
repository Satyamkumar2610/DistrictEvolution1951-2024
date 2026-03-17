"use client";

import React, { useState, useRef } from "react";
import Map, { Source, Layer, MapRef } from "react-map-gl/maplibre";
import * as turf from "@turf/turf";
import { UploadCloud, Loader2, AlertCircle, FileJson } from "lucide-react";
import 'maplibre-gl/dist/maplibre-gl.css';
import { FeatureCollection, Feature, Geometry, Polygon, MultiPolygon } from "geojson";



type AnalysisState = "idle" | "processing_client" | "processing_server" | "success" | "error";

interface GeoJsonResponse {
    transferredArea: FeatureCollection<Geometry>;
    remainingArea: FeatureCollection<Geometry>;
    parentOriginal: FeatureCollection<Geometry>;
    childOriginal: FeatureCollection<Geometry>;
}

export default function DistrictSplitAnalyzer() {
    const mapRef = useRef<MapRef>(null);

    const [parentFile, setParentFile] = useState<File | null>(null);
    const [childFile, setChildFile] = useState<File | null>(null);

    // Parsed GeoJSON states
    const [parentGeoJson, setParentGeoJson] = useState<FeatureCollection<Geometry> | null>(null);
    const [childGeoJson, setChildGeoJson] = useState<FeatureCollection<Geometry> | null>(null);

    // Analysis Result States
    const [results, setResults] = useState<GeoJsonResponse | null>(null);
    const [serverStats, setServerStats] = useState<{ transferredAreaSqKm: number, remainingAreaSqKm: number } | null>(null);

    const [status, setStatus] = useState<AnalysisState>("idle");
    const [errorMessage, setErrorMessage] = useState<string>("");

    const [viewState, setViewState] = useState({
        longitude: 78.9629,
        latitude: 20.5937,
        zoom: 4
    });

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>, type: "parent" | "child") => {
        const file = e.target.files?.[0];
        if (!file) return;

        if (type === "parent") setParentFile(file);
        else setChildFile(file);

        try {
            const text = await file.text();
            const geojson = JSON.parse(text);

            // Basic validation
            if (geojson.type !== "FeatureCollection" && geojson.type !== "Feature") {
                throw new Error("Invalid GeoJSON format. Must be a Feature or FeatureCollection.");
            }

            // Normalize to FeatureCollection for consistency
            const normalized: FeatureCollection<Geometry> = geojson.type === "FeatureCollection"
                ? geojson
                : turf.featureCollection([geojson as Feature<Geometry>]);

            if (type === "parent") {
                setParentGeoJson(normalized);
            } else {
                setChildGeoJson(normalized);
            }

            // zoom to the uploaded feature
            if (mapRef.current) {
                const bbox = turf.bbox(normalized);
                mapRef.current.fitBounds([
                    [bbox[0], bbox[1]],
                    [bbox[2], bbox[3]]
                ], { padding: 40, duration: 1000 });
            }
        } catch (err: any /* eslint-disable-line @typescript-eslint/no-explicit-any */) {
            setErrorMessage(`Failed to parse ${type} file: ${err.message}`);
            setStatus("error");
        }
    };

    const processSplit = async () => {
        if (!parentGeoJson || !childGeoJson) {
            setErrorMessage("Please upload both Parent and Child boundaries.");
            setStatus("error");
            return;
        }

        setStatus("processing_client");
        setErrorMessage("");

        try {
            // STEP 1: Turf.js Client-Side Processing (Fast visual feedback)
            // Combine all features into single multi-polygons if needed for simpler intersection

            // For now, assume single features for simplicity in Turf, but we should map over them ideally.
            const parentPoly = parentGeoJson.features[0] as Feature<Polygon | MultiPolygon>;
            const childPoly = childGeoJson.features[0] as Feature<Polygon | MultiPolygon>;

            if (!parentPoly || !childPoly) throw new Error("Missing features in GeoJSON");

            // 1. Transferred Area (Intersection)
            const intersection = turf.intersect(turf.featureCollection([parentPoly, childPoly]));

            // 2. Remaining Area (Difference)
            const difference = turf.difference(turf.featureCollection([parentPoly, childPoly]));

            if (!intersection) {
                throw new Error("The Child district does not intersect with the Parent district.");
            }

            const transferredAreaFc = turf.featureCollection([intersection as unknown as Feature<Geometry>]);
            const remainingAreaFc = difference ? turf.featureCollection([difference as unknown as Feature<Geometry>]) : turf.featureCollection([]);

            setResults({
                transferredArea: transferredAreaFc,
                remainingArea: remainingAreaFc,
                parentOriginal: parentGeoJson,
                childOriginal: childGeoJson
            });

            // Zoom to the intersection
            if (mapRef.current) {
                const bbox = turf.bbox(transferredAreaFc);
                mapRef.current.fitBounds([
                    [bbox[0], bbox[1]],
                    [bbox[2], bbox[3]]
                ], { padding: 60, duration: 1000 });
            }

            // STEP 2: Send to backend for accurate EPSG:7755 area calculation
            setStatus("processing_server");

            const formData = new FormData();
            formData.append("parent_geojson", new Blob([JSON.stringify(parentGeoJson)], { type: "application/json" }));
            formData.append("child_geojson", new Blob([JSON.stringify(childGeoJson)], { type: "application/json" }));

            // Using the existing API backend URL
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const res = await fetch(`${apiUrl}/api/v1/spatial/calculate-split`, {
                method: "POST",
                body: formData,
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.detail || "Backend analysis failed");
            }

            const data = await res.json();
            setServerStats({
                transferredAreaSqKm: data.transferred_area_sqkm,
                remainingAreaSqKm: data.remaining_area_sqkm
            });

            setStatus("success");

        } catch (err: any /* eslint-disable-line @typescript-eslint/no-explicit-any */) {
            console.error(err);
            setErrorMessage(err.message || "An error occurred during analysis.");
            setStatus("error");
        }
    };

    // Rendering Logic
    return (
        <div className="flex flex-col h-full bg-white dark:bg-gray-900 rounded-lg shadow-xl overflow-hidden min-h-[800px]">
            {/* Header */}
            <div className="p-6 border-b border-gray-200 dark:border-gray-800">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Dynamic District Split Analyzer</h2>
                <p className="text-gray-500 dark:text-gray-400 mt-1">
                    Upload Parent and Child boundaries to dynamically compute overlapping and remaining areas with high-precision equal-area projection accuracy.
                </p>
            </div>

            <div className="flex flex-1 flex-col lg:flex-row">
                {/* Sidebar Controls */}
                <div className="w-full lg:w-1/3 p-6 flex flex-col gap-6 overflow-y-auto border-r border-gray-200 dark:border-gray-800">

                    {/* Error Alert */}
                    {status === "error" && (
                        <div className="p-4 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 rounded-lg flex items-start gap-3">
                            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                            <p className="text-sm font-medium">{errorMessage}</p>
                        </div>
                    )}

                    {/* Parent Upload */}
                    <div className="space-y-3">
                        <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300">
                            1. Parent District (Original geometry)
                        </label>
                        <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-slate-300 border-dashed rounded-lg cursor-pointer bg-slate-50 dark:hover:bg-slate-800 dark:bg-slate-900 hover:bg-slate-100 dark:border-slate-700 transition-colors">
                            <div className="flex flex-col items-center justify-center pt-5 pb-6">
                                {parentFile ? (
                                    <>
                                        <FileJson className="w-8 h-8 text-emerald-500 mb-2" />
                                        <p className="text-sm text-gray-500 dark:text-gray-400 font-medium">{parentFile.name}</p>
                                    </>
                                ) : (
                                    <>
                                        <UploadCloud className="w-8 h-8 text-gray-400 mb-2" />
                                        <p className="text-sm text-gray-500 dark:text-gray-400"><span className="font-semibold">Click to upload</span> GeoJSON</p>
                                    </>
                                )}
                            </div>
                            <input type="file" className="hidden" accept=".geojson,.json" onChange={(e) => handleFileUpload(e, "parent")} />
                        </label>
                    </div>

                    {/* Child Upload */}
                    <div className="space-y-3">
                        <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300">
                            2. Child District (New split geometry)
                        </label>
                        <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-slate-300 border-dashed rounded-lg cursor-pointer bg-slate-50 dark:hover:bg-slate-800 dark:bg-slate-900 hover:bg-slate-100 dark:border-slate-700 transition-colors">
                            <div className="flex flex-col items-center justify-center pt-5 pb-6">
                                {childFile ? (
                                    <>
                                        <FileJson className="w-8 h-8 text-blue-500 mb-2" />
                                        <p className="text-sm text-gray-500 dark:text-gray-400 font-medium">{childFile.name}</p>
                                    </>
                                ) : (
                                    <>
                                        <UploadCloud className="w-8 h-8 text-gray-400 mb-2" />
                                        <p className="text-sm text-gray-500 dark:text-gray-400"><span className="font-semibold">Click to upload</span> GeoJSON</p>
                                    </>
                                )}
                            </div>
                            <input type="file" className="hidden" accept=".geojson,.json" onChange={(e) => handleFileUpload(e, "child")} />
                        </label>
                    </div>

                    {/* Analyze Button */}
                    <button
                        onClick={processSplit}
                        disabled={!parentFile || !childFile || status === "processing_client" || status === "processing_server"}
                        className="w-full mt-4 py-3 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-semibold rounded-lg shadow-sm transition-all flex items-center justify-center gap-2 disabled:cursor-not-allowed"
                    >
                        {(status === "processing_client" || status === "processing_server") ? (
                            <><Loader2 className="w-5 h-5 animate-spin" /> Processing...</>
                        ) : "Analyze Split"}
                    </button>

                    {/* Results Panel */}
                    {status === "success" && serverStats && (
                        <div className="mt-8 p-5 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-xl">
                            <h3 className="text-lg font-bold text-emerald-900 dark:text-emerald-100 mb-4">Precision Analytics</h3>
                            <div className="space-y-4">
                                <div>
                                    <p className="text-sm text-emerald-700 dark:text-emerald-400">Transferred Area (Intersection)</p>
                                    <p className="text-2xl font-black text-emerald-900 dark:text-emerald-50">
                                        {serverStats.transferredAreaSqKm.toLocaleString(undefined, { maximumFractionDigits: 2 })} <span className="text-sm font-medium">sq km</span>
                                    </p>
                                </div>
                                <div className="h-px bg-emerald-200 dark:bg-emerald-800/50 w-full" />
                                <div>
                                    <p className="text-sm text-emerald-700 dark:text-emerald-400">Remaining Parent Area (Difference)</p>
                                    <p className="text-2xl font-black text-emerald-900 dark:text-emerald-50">
                                        {serverStats.remainingAreaSqKm.toLocaleString(undefined, { maximumFractionDigits: 2 })} <span className="text-sm font-medium">sq km</span>
                                    </p>
                                </div>

                                <div className="mt-2 pt-2 text-xs text-emerald-600 dark:text-emerald-500 flex items-center gap-1">
                                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                    Calculated using backend EPSG:7755 Equal Area Projection
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Map Interface */}
                <div className="flex-1 w-full bg-slate-100 relative min-h-[400px]">
                    <Map
                        ref={mapRef}
                        id="split-map"
                        initialViewState={viewState}
                        onMove={(evt) => setViewState(evt.viewState)}
                        mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
                        style={{ width: "100%", height: "100%", borderRadius: "0.75rem" }}
                    >
                        {/* 1. Parent Only (Before Analysis) */}
                        {parentGeoJson && !results && (
                            <Source id="parent-source" type="geojson" data={parentGeoJson}>
                                <Layer
                                    id="parent-fill"
                                    type="fill"
                                    paint={{
                                        "fill-color": "#94a3b8", // slate-400
                                        "fill-opacity": 0.3
                                    }}
                                />
                                <Layer
                                    id="parent-line"
                                    type="line"
                                    paint={{
                                        "line-color": "#475569", // slate-600
                                        "line-width": 2,
                                        "line-dasharray": [2, 2]
                                    }}
                                />
                            </Source>
                        )}

                        {/* 2. Child Only (Before Analysis) */}
                        {childGeoJson && !results && (
                            <Source id="child-source" type="geojson" data={childGeoJson}>
                                <Layer
                                    id="child-fill"
                                    type="fill"
                                    paint={{
                                        "fill-color": "#60a5fa", // blue-400
                                        "fill-opacity": 0.4
                                    }}
                                />
                                <Layer
                                    id="child-line"
                                    type="line"
                                    paint={{
                                        "line-color": "#2563eb", // blue-600
                                        "line-width": 2
                                    }}
                                />
                            </Source>
                        )}

                        {/* 3. Results Rendering */}
                        {results && (
                            <>
                                {/* Remaining Area */}
                                <Source id="remaining-source" type="geojson" data={results.remainingArea}>
                                    <Layer
                                        id="remaining-fill"
                                        type="fill"
                                        paint={{
                                            "fill-color": "#f59e0b", // amber-500
                                            "fill-opacity": 0.6
                                        }}
                                    />
                                    <Layer
                                        id="remaining-line"
                                        type="line"
                                        paint={{
                                            "line-color": "#d97706", // amber-600
                                            "line-width": 2
                                        }}
                                    />
                                </Source>

                                {/* Transferred Area */}
                                <Source id="transferred-source" type="geojson" data={results.transferredArea}>
                                    <Layer
                                        id="transferred-fill"
                                        type="fill"
                                        paint={{
                                            "fill-color": "#10b981", // emerald-500
                                            "fill-opacity": 0.7
                                        }}
                                    />
                                    <Layer
                                        id="transferred-line"
                                        type="line"
                                        paint={{
                                            "line-color": "#059669", // emerald-600
                                            "line-width": 2
                                        }}
                                    />
                                </Source>
                            </>
                        )}
                    </Map>

                    {/* Map Legend Overlay */}
                    {results && (
                        <div className="absolute bottom-6 left-6 p-4 rounded-lg bg-white/90 dark:bg-slate-900/90 shadow-lg backdrop-blur-sm border border-slate-200 dark:border-slate-800">
                            <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200 mb-3">Map Legend</h4>
                            <div className="space-y-2">
                                <div className="flex items-center gap-2">
                                    <div className="w-4 h-4 rounded bg-emerald-500 opacity-70 border-2 border-emerald-600" />
                                    <span className="text-sm text-slate-600 dark:text-slate-400">Transferred Area</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="w-4 h-4 rounded bg-amber-500 opacity-60 border-2 border-amber-600" />
                                    <span className="text-sm text-slate-600 dark:text-slate-400">Remaining Parent Area</span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
