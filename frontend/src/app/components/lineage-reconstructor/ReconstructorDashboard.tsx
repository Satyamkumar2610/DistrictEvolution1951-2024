"use client";

import React, { useState, useEffect, useRef } from "react";
import Map, { MapRef } from "react-map-gl/maplibre";
import { Loader2, Search, Layers } from "lucide-react";
import "maplibre-gl/dist/maplibre-gl.css";

import EpochTimeline from "./EpochTimeline";
import ReconstructedMapLayer from "./ReconstructedMapLayer";
import YieldReconstructionChart from "./YieldReconstructionChart";
import EpochMetricsPanel from "./EpochMetricsPanel";

const API_URL = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "https://i-ascap.onrender.com";

interface SearchResult {
    cdk: string;
    display_name: string;
    state: string;
    era: number;
    is_root: boolean;
}

const FEATURED_EXAMPLES: SearchResult[] = [
    { cdk: "WB_24parg_1961", display_name: "24 Parganas", state: "West Bengal", era: 1961, is_root: true },
    { cdk: "MH_medinipur_1951", display_name: "Medinipur", state: "Maharashtra/WB", era: 1951, is_root: true },
    { cdk: "DL_delhi_1951", display_name: "Delhi", state: "Delhi", era: 1951, is_root: true }
];

export default function ReconstructorDashboard() {
    const mapRef = useRef<MapRef>(null);

    const [searchQuery, setSearchQuery] = useState("");
    const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [showResults, setShowResults] = useState(false);

    const [selectedCdk, setSelectedCdk] = useState("");
    const [crop, setCrop] = useState("rice");
    
    const [epochs, setEpochs] = useState<any[]>([]);
    const [activeEpochIndex, setActiveEpochIndex] = useState<number>(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    // Debounced search
    useEffect(() => {
        if (searchQuery.length < 2) {
            setSearchResults([]);
            return;
        }
        
        const delay = setTimeout(async () => {
            setIsSearching(true);
            try {
                const res = await fetch(`${API_URL}/api/v1/reconstruct/search?q=${encodeURIComponent(searchQuery)}`);
                if (res.ok) {
                    const data = await res.json();
                    setSearchResults(data);
                }
            } catch (err) {
                console.error("Search failed", err);
            } finally {
                setIsSearching(false);
            }
        }, 400);

        return () => clearTimeout(delay);
    }, [searchQuery]);

    const handleSelectResult = (cdk: string, name: string) => {
        setSelectedCdk(cdk);
        setSearchQuery(name);
        setShowResults(false);
        runReconstruction(cdk);
    };

    const runReconstruction = async (cdk: string) => {
        if (!cdk) return;
        setError("");
        setLoading(true);
        try {
            const res = await fetch(`${API_URL}/api/v1/reconstruct/${cdk}?crop=${crop}`);
            if (!res.ok) throw new Error("Reconstruction failed to load");
            
            const data = await res.json();
            setEpochs(data.epochs || []);
            setActiveEpochIndex(0);
        } catch (err: any) {
            setError(err.message || "Failed");
        } finally {
            setLoading(false);
        }
    };

    // Listen to arrow keys
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (epochs.length > 0) {
                if (e.key === "ArrowRight") {
                    setActiveEpochIndex(prev => Math.min(prev + 1, epochs.length - 1));
                } else if (e.key === "ArrowLeft") {
                    setActiveEpochIndex(prev => Math.max(prev - 1, 0));
                }
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [epochs]);

    const activeEpoch = epochs[activeEpochIndex];

    return (
        <div className="flex flex-col h-full bg-slate-50 min-h-screen">
            {/* Header */}
            <div className="px-6 py-5 bg-white border-b border-slate-200 flex justify-between items-center shadow-sm">
                <div>
                    <h2 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                        <Layers className="w-6 h-6 text-indigo-500" />
                        Lineage Reconstructor
                    </h2>
                    <p className="text-slate-500 mt-1 text-sm">
                        Observe district fragmentations chronologically with strictly aggregated yield panels.
                    </p>
                </div>
            </div>

            <div className="max-w-7xl mx-auto w-full p-4 lg:p-6 flex flex-col gap-6">
                
                {/* Search Bar */}
                <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200 relative">
                    <div className="flex flex-col md:flex-row gap-4 items-end">
                        <div className="relative flex-1 w-full">
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Target District</label>
                            <div className="relative">
                                <Search className="absolute left-3 top-2.5 w-5 h-5 text-slate-400" />
                                <input
                                    type="text"
                                    value={searchQuery}
                                    onChange={(e) => {
                                        setSearchQuery(e.target.value);
                                        setShowResults(true);
                                    }}
                                    onFocus={() => setShowResults(true)}
                                    onBlur={() => setTimeout(() => setShowResults(false), 200)}
                                    placeholder="Search e.g. WB_24parg_1961"
                                    className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                                />
                                {isSearching && <Loader2 className="absolute right-3 top-2.5 w-5 h-5 animate-spin text-slate-400" />}
                            </div>

                            {/* Dropdown */}
                            {showResults && (
                                <div className="absolute top-full left-0 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-xl z-50 max-h-64 overflow-y-auto">
                                    {searchQuery.length < 2 ? (
                                        <div className="py-2">
                                            <p className="px-4 py-1 text-xs font-bold text-slate-400 uppercase">Featured Examples</p>
                                            {FEATURED_EXAMPLES.map(r => (
                                                <div 
                                                    key={r.cdk} 
                                                    onClick={() => handleSelectResult(r.cdk, r.display_name)}
                                                    className="px-4 py-3 hover:bg-slate-50 cursor-pointer border-b border-slate-100 last:border-0"
                                                >
                                                    <p className="font-semibold text-slate-800 text-sm">{r.display_name}</p>
                                                    <p className="text-xs text-slate-500 font-mono mt-0.5">{r.cdk} • {r.state} • Era {r.era}</p>
                                                </div>
                                            ))}
                                        </div>
                                    ) : searchResults.length > 0 ? (
                                        searchResults.map(r => (
                                            <div 
                                                key={r.cdk} 
                                                onClick={() => handleSelectResult(r.cdk, r.display_name)}
                                                className="px-4 py-3 hover:bg-slate-50 cursor-pointer border-b border-slate-100 last:border-0"
                                            >
                                                <p className="font-semibold text-slate-800 text-sm whitespace-nowrap overflow-hidden text-ellipsis">{r.display_name}</p>
                                                <p className="text-xs text-slate-500 font-mono mt-0.5">{r.cdk} • {r.state} • Era {r.era}</p>
                                            </div>
                                        ))
                                    ) : !isSearching ? (
                                        <div className="p-4 text-sm text-slate-500">No districts found matching &quot;{searchQuery}&quot;</div>
                                    ) : null}
                                </div>
                            )}
                        </div>

                        <div className="w-full md:w-48">
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Crop</label>
                            <select 
                                value={crop} 
                                onChange={(e) => {
                                    setCrop(e.target.value);
                                    if (selectedCdk) runReconstruction(selectedCdk);
                                }}
                                className="w-full px-3 py-2.5 border border-slate-300 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                            >
                                <option value="rice">Rice</option>
                                <option value="wheat">Wheat</option>
                                <option value="maize">Maize</option>
                            </select>
                        </div>
                    </div>
                </div>

                {error && (
                    <div className="bg-red-50 text-red-700 p-4 rounded-lg border border-red-200">{error}</div>
                )}
                {loading && (
                    <div className="flex justify-center p-12 bg-white rounded-xl border border-slate-200 shadow-sm">
                        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
                        <span className="ml-3 text-slate-600 font-medium my-auto">Reconstructing lineage...</span>
                    </div>
                )}

                {epochs.length > 0 && !loading && (
                    <div className="flex flex-col gap-6">
                        
                        {/* Map & Chart Split Row */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[400px]">
                            {/* Map panel */}
                            <div className="bg-white border text-center border-slate-200 rounded-xl shadow-sm overflow-hidden relative group h-full">
                                <Map
                                    ref={mapRef}
                                    initialViewState={{ longitude: 78.9629, latitude: 20.5937, zoom: 4 }}
                                    mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
                                    style={{ width: "100%", height: "100%" }}
                                >
                                    {activeEpoch && <ReconstructedMapLayer epoch={activeEpoch} />}
                                </Map>
                            </div>

                            {/* Chart Panel */}
                            <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm flex flex-col h-full">
                                <YieldReconstructionChart 
                                    epochs={epochs} 
                                    activeEpochIndex={activeEpochIndex} 
                                    onEpochChange={setActiveEpochIndex} 
                                />
                            </div>
                        </div>

                        {/* Timeline */}
                        <EpochTimeline 
                            epochs={epochs} 
                            activeEpochIndex={activeEpochIndex} 
                            onEpochChange={setActiveEpochIndex} 
                        />

                        {/* Metrics panel */}
                        <EpochMetricsPanel 
                            epoch={activeEpoch} 
                            crop={crop}
                        />

                    </div>
                )}

            </div>
        </div>
    );
}
