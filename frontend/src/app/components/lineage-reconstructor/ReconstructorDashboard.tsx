"use client";

import React, { useState, useRef } from "react";
import Map, { Source, Layer, MapRef } from "react-map-gl/maplibre";
import * as turf from "@turf/turf";
import { Loader2, ArrowRight, Layers, MapPin } from "lucide-react";
import "maplibre-gl/dist/maplibre-gl.css";
import YieldReconstructionChart from "./YieldReconstructionChart";

const API_URL = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "https://i-ascap.onrender.com";

interface ReconstructorResult {
    base_cdk: string;
    crop: string;
    reconstructed_geometry: any;
    leaf_descendants: string[];
    timeline: any[];
}

export default function ReconstructorDashboard() {
    const mapRef = useRef<MapRef>(null);

    const [cdk, setCdk] = useState("");
    const [crop, setCrop] = useState("rice");
    const [startYear, setStartYear] = useState(1970);
    const [endYear, setEndYear] = useState(2020);

    const [result, setResult] = useState<ReconstructorResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const [viewState, setViewState] = useState({
        longitude: 78.9629,
        latitude: 20.5937,
        zoom: 4,
    });

    const runAnalysis = async () => {
        if (!cdk.trim()) {
            setError("Please enter a valid Target District CDK");
            return;
        }

        setError("");
        setLoading(true);
        setResult(null);

        try {
            const res = await fetch(`${API_URL}/api/v1/reconstructor/${cdk}?crop=${crop}&start_year=${startYear}&end_year=${endYear}`, {
                headers: { "Content-Type": "application/json" }
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: "Analysis failed" }));
                throw new Error(err.detail || "Request failed");
            }

            const data: ReconstructorResult = await res.json();
            setResult(data);

            if (data.reconstructed_geometry && mapRef.current) {
                const bbox = turf.bbox(data.reconstructed_geometry);
                mapRef.current.fitBounds(
                    [[bbox[0], bbox[1]], [bbox[2], bbox[3]]],
                    { padding: 60, duration: 1000 }
                );
            }
        } catch (err: any) {
            setError(err.message || "Failed to fetch reconstruction logic.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-white rounded-xl shadow-xl overflow-hidden border border-slate-200">
            {/* Header */}
            <div className="px-6 py-5 border-b border-slate-200 bg-gradient-to-r from-indigo-50 to-slate-50">
                <h2 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                    <Layers className="w-6 h-6 text-indigo-500" />
                    Lineage Reconstructor
                </h2>
                <p className="text-slate-500 mt-1 text-sm">
                    Reconstruct historical district geometries forwards through time. View continuous yield timeline of the combined landmass.
                </p>
            </div>

            <div className="flex flex-1 flex-col lg:flex-row overflow-hidden">
                {/* Left Panel */}
                <div className="w-full lg:w-[400px] p-5 flex flex-col gap-6 overflow-y-auto border-r border-slate-200 bg-slate-50/50">
                    
                    {error && (
                        <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm border border-red-200">
                            {error}
                        </div>
                    )}

                    <div className="space-y-4">
                        <div>
                            <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Target District CDK</label>
                            <input
                                type="text"
                                value={cdk}
                                onChange={(e) => setCdk(e.target.value)}
                                placeholder="e.g. WB_24parg_1961"
                                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Crop</label>
                                <select 
                                    value={crop} 
                                    onChange={(e) => setCrop(e.target.value)}
                                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white outline-none focus:ring-2 focus:ring-indigo-500"
                                >
                                    <option value="rice">Rice</option>
                                    <option value="wheat">Wheat</option>
                                    <option value="maize">Maize</option>
                                </select>
                            </div>
                            <div className="flex gap-2">
                                <div className="flex-1">
                                    <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">From</label>
                                    <input type="number" value={startYear} onChange={e => setStartYear(Number(e.target.value))} className="w-full px-2 py-2 border rounded-lg text-sm outline-none" />
                                </div>
                                <div className="flex-1">
                                    <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">To</label>
                                    <input type="number" value={endYear} onChange={e => setEndYear(Number(e.target.value))} className="w-full px-2 py-2 border rounded-lg text-sm outline-none" />
                                </div>
                            </div>
                        </div>

                        <button
                            onClick={runAnalysis}
                            disabled={loading || !cdk}
                            className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-semibold rounded-lg shadow-sm transition flex items-center justify-center gap-2"
                        >
                            {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Reconstructing...</> : <><ArrowRight className="w-4 h-4" /> Reconstruct Timeline</>}
                        </button>
                    </div>

                    {result && result.timeline && (
                        <div className="flex-1 flex flex-col pt-4 border-t border-slate-200">
                            <YieldReconstructionChart data={result.timeline} crop={result.crop} />
                            
                            <div className="mt-6">
                                <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1">
                                    <MapPin className="w-3.5 h-3.5" /> Constituent Leaves ({result.leaf_descendants.length})
                                </h4>
                                <div className="bg-white rounded-lg border border-slate-200 p-3 max-h-32 overflow-y-auto">
                                    <div className="flex flex-wrap gap-2">
                                        {result.leaf_descendants.map(leaf => (
                                            <span key={leaf} className="px-2 py-1 bg-slate-100 text-slate-600 text-xs rounded-md font-medium border border-slate-200">
                                                {leaf}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Right Panel Map */}
                <div className="flex-1 w-full bg-slate-100 relative min-h-[400px]">
                    <Map
                        ref={mapRef}
                        initialViewState={viewState}
                        onMove={(evt) => setViewState(evt.viewState)}
                        mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
                        style={{ width: "100%", height: "100%" }}
                    >
                        {result && result.reconstructed_geometry && (
                            <Source id="reconstructed" type="geojson" data={result.reconstructed_geometry}>
                                <Layer 
                                    id="reconstructed-fill" 
                                    type="fill" 
                                    paint={{ "fill-color": "#4f46e5", "fill-opacity": 0.4 }} 
                                />
                                <Layer 
                                    id="reconstructed-line" 
                                    type="line" 
                                    paint={{ "line-color": "#312e81", "line-width": 2, "line-dasharray": [2, 2] }} 
                                />
                            </Source>
                        )}
                    </Map>
                </div>
            </div>
        </div>
    );
}
