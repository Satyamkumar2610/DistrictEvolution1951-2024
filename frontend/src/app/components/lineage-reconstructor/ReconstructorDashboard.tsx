"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import Map, { Source, Layer, NavigationControl, MapRef } from "react-map-gl/maplibre";
import { Loader2, Search, Layers, TrendingUp, TrendingDown, Minus, BarChart3, MapPin, GitBranch, Calendar, ChevronRight } from "lucide-react";
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

/* ---------- 50+ Featured Districts grouped by state ---------- */
const FEATURED_EXAMPLES: SearchResult[] = [
    // West Bengal
    { cdk: "WB_24parg_1961", display_name: "24 Parganas", state: "West Bengal", era: 1961, is_root: true },
    { cdk: "WB_medini_1951", display_name: "Medinipur", state: "West Bengal", era: 1951, is_root: true },
    { cdk: "WB_barddh_1951", display_name: "Bardhaman", state: "West Bengal", era: 1951, is_root: true },
    { cdk: "WB_darjil_1971", display_name: "Darjeeling", state: "West Bengal", era: 1971, is_root: true },
    // Uttar Pradesh
    { cdk: "UP_meerut_1951", display_name: "Meerut", state: "Uttar Pradesh", era: 1951, is_root: true },
    { cdk: "UP_buland_1971", display_name: "Bulandshahr", state: "Uttar Pradesh", era: 1971, is_root: true },
    { cdk: "UP_allaha_1951", display_name: "Allahabad", state: "Uttar Pradesh", era: 1951, is_root: true },
    { cdk: "UP_gorakh_1981", display_name: "Gorakhpur", state: "Uttar Pradesh", era: 1981, is_root: true },
    { cdk: "UP_varana_1951", display_name: "Varanasi", state: "Uttar Pradesh", era: 1951, is_root: true },
    { cdk: "UP_kanpur_1951", display_name: "Kanpur", state: "Uttar Pradesh", era: 1951, is_root: true },
    // Bihar
    { cdk: "BR_patna_1971", display_name: "Patna", state: "Bihar", era: 1971, is_root: true },
    { cdk: "BR_darbha_1971", display_name: "Darbhanga", state: "Bihar", era: 1971, is_root: true },
    { cdk: "BR_gaya_1971", display_name: "Gaya", state: "Bihar", era: 1971, is_root: true },
    { cdk: "BR_purnea_1971", display_name: "Purnea", state: "Bihar", era: 1971, is_root: true },
    // Madhya Pradesh
    { cdk: "MP_jabalp_1991", display_name: "Jabalpur", state: "Madhya Pradesh", era: 1991, is_root: true },
    { cdk: "MP_sagar_1951", display_name: "Sagar", state: "Madhya Pradesh", era: 1951, is_root: true },
    { cdk: "MP_gird_1951", display_name: "Gird", state: "Madhya Pradesh", era: 1951, is_root: true },
    // Maharashtra
    { cdk: "MH_thane_1971", display_name: "Thane", state: "Maharashtra", era: 1971, is_root: true },
    { cdk: "MH_pune_1951", display_name: "Pune", state: "Maharashtra", era: 1951, is_root: true },
    { cdk: "MH_nasik_1971", display_name: "Nashik", state: "Maharashtra", era: 1971, is_root: true },
    { cdk: "MH_aurang_1981", display_name: "Aurangabad", state: "Maharashtra", era: 1981, is_root: true },
    // Gujarat
    { cdk: "GJ_surat_1961", display_name: "Surat", state: "Gujarat", era: 1961, is_root: true },
    { cdk: "GJ_ahmeda_1961", display_name: "Ahmedabad", state: "Gujarat", era: 1961, is_root: true },
    { cdk: "GJ_rajkot_1961", display_name: "Rajkot", state: "Gujarat", era: 1961, is_root: true },
    { cdk: "GJ_kutch_1971", display_name: "Kutch", state: "Gujarat", era: 1971, is_root: true },
    // Rajasthan
    { cdk: "RJ_jaipur_1951", display_name: "Jaipur", state: "Rajasthan", era: 1951, is_root: true },
    { cdk: "RJ_kota_1951", display_name: "Kota", state: "Rajasthan", era: 1951, is_root: true },
    { cdk: "RJ_udaipu_1951", display_name: "Udaipur", state: "Rajasthan", era: 1951, is_root: true },
    // Tamil Nadu
    { cdk: "TN_madura_1951", display_name: "Madurai", state: "Tamil Nadu", era: 1951, is_root: true },
    { cdk: "TN_coimba_1951", display_name: "Coimbatore", state: "Tamil Nadu", era: 1951, is_root: true },
    { cdk: "TN_salem_1961", display_name: "Salem", state: "Tamil Nadu", era: 1961, is_root: true },
    { cdk: "TN_chenna_1991", display_name: "Chennai", state: "Tamil Nadu", era: 1991, is_root: true },
    // Karnataka
    { cdk: "KA_dharwa_1971", display_name: "Dharwad", state: "Karnataka", era: 1971, is_root: true },
    { cdk: "KA_bangal_1981", display_name: "Bangalore", state: "Karnataka", era: 1981, is_root: true },
    { cdk: "KA_mysuru_1991", display_name: "Mysuru", state: "Karnataka", era: 1991, is_root: true },
    // Haryana
    { cdk: "HR_hisar_1951", display_name: "Hisar", state: "Haryana", era: 1951, is_root: true },
    { cdk: "HR_rohtak_1951", display_name: "Rohtak", state: "Haryana", era: 1951, is_root: true },
    { cdk: "HR_karnal_1951", display_name: "Karnal", state: "Haryana", era: 1951, is_root: true },
    // Punjab
    { cdk: "PB_bhatin_1951", display_name: "Bhatinda", state: "Punjab", era: 1951, is_root: true },
    { cdk: "PB_firozp_1951", display_name: "Firozpur", state: "Punjab", era: 1951, is_root: true },
    { cdk: "PB_jaland_1971", display_name: "Jalandhar", state: "Punjab", era: 1971, is_root: true },
    // Odisha
    { cdk: "OD_cuttac_1991", display_name: "Cuttack", state: "Odisha", era: 1991, is_root: true },
    { cdk: "OD_ganjam_1991", display_name: "Ganjam", state: "Odisha", era: 1991, is_root: true },
    // Jharkhand
    { cdk: "JH_ranchi_1981", display_name: "Ranchi", state: "Jharkhand", era: 1981, is_root: true },
    { cdk: "JH_hazari_1971", display_name: "Hazaribag", state: "Jharkhand", era: 1971, is_root: true },
    // Andhra + Telangana
    { cdk: "AP_guntur_1951", display_name: "Guntur", state: "Andhra Pradesh", era: 1951, is_root: true },
    { cdk: "TG_hydera_1971", display_name: "Hyderabad", state: "Telangana", era: 1971, is_root: true },
    { cdk: "TG_warang_1951", display_name: "Warangal", state: "Telangana", era: 1951, is_root: true },
    // Assam & NE
    { cdk: "AS_kamrup_1981", display_name: "Kamrup", state: "Assam", era: 1981, is_root: true },
    { cdk: "MN_manipu_1951", display_name: "Manipur", state: "Manipur", era: 1951, is_root: true },
    { cdk: "TR_tripur_1951", display_name: "Tripura", state: "Tripura", era: 1951, is_root: true },
    // Delhi & NCR
    { cdk: "DL_delhi_1991", display_name: "Delhi", state: "Delhi", era: 1991, is_root: true },
    // J&K
    { cdk: "JK_jammua_1951", display_name: "Jammu & Kashmir", state: "J&K", era: 1951, is_root: true },
    // Uttarakhand
    { cdk: "UK_dehrad_1991", display_name: "Dehradun", state: "Uttarakhand", era: 1991, is_root: true },
    { cdk: "UK_nainit_1971", display_name: "Nainital", state: "Uttarakhand", era: 1971, is_root: true },
    // Sikkim
    { cdk: "SK_sikkim_1971", display_name: "Sikkim", state: "Sikkim", era: 1971, is_root: true },
    // Chhattisgarh
    { cdk: "CG_raipur_1991", display_name: "Raipur", state: "Chhattisgarh", era: 1991, is_root: true },
    { cdk: "CG_bastar_1991", display_name: "Bastar", state: "Chhattisgarh", era: 1991, is_root: true },
];

/* ---------- Insights computed from epoch data ---------- */
interface Insight {
    icon: React.ReactNode;
    label: string;
    value: string;
    subtext?: string;
    color: string;
}

function computeInsights(epochs: any[], crop: string): Insight[] {
    if (!epochs || epochs.length === 0) return [];
    const insights: Insight[] = [];

    // Flatten all metrics
    const allMetrics = epochs.flatMap((ep: any) => ep.metrics || []);
    const withYield = allMetrics.filter((m: any) => m.collective_yield != null);

    // 1. Total fragmentations
    const splitCount = epochs.length - 1;
    insights.push({
        icon: <GitBranch className="w-4 h-4" />,
        label: "Fragmentations",
        value: `${splitCount}`,
        subtext: splitCount === 0 ? "No splits recorded" : `${splitCount} split${splitCount > 1 ? 's' : ''} since ${epochs[0]?.year_start || '?'}`,
        color: "text-violet-400",
    });

    // 2. Peak yield
    if (withYield.length > 0) {
        const peak = withYield.reduce((a: any, b: any) => a.collective_yield > b.collective_yield ? a : b);
        insights.push({
            icon: <TrendingUp className="w-4 h-4" />,
            label: "Peak Yield",
            value: `${Math.round(peak.collective_yield).toLocaleString()} kg/ha`,
            subtext: `in ${peak.year}`,
            color: "text-emerald-400",
        });
    }

    // 3. Yield trend (first decade vs last decade)
    if (withYield.length >= 5) {
        const first5 = withYield.slice(0, 5).reduce((s: number, m: any) => s + m.collective_yield, 0) / 5;
        const last5 = withYield.slice(-5).reduce((s: number, m: any) => s + m.collective_yield, 0) / 5;
        const pctChange = ((last5 - first5) / first5) * 100;
        const trending = pctChange > 5 ? "Increasing" : pctChange < -5 ? "Decreasing" : "Stable";
        const trendIcon = pctChange > 5 ? <TrendingUp className="w-4 h-4" /> : pctChange < -5 ? <TrendingDown className="w-4 h-4" /> : <Minus className="w-4 h-4" />;
        insights.push({
            icon: trendIcon,
            label: "Overall Trend",
            value: trending,
            subtext: `${pctChange > 0 ? '+' : ''}${pctChange.toFixed(1)}% change`,
            color: pctChange > 5 ? "text-emerald-400" : pctChange < -5 ? "text-red-400" : "text-amber-400",
        });
    }

    // 4. Data coverage
    const totalYears = allMetrics.length;
    const coveredYears = withYield.length;
    const dataCoverage = totalYears > 0 ? (coveredYears / totalYears) * 100 : 0;
    insights.push({
        icon: <BarChart3 className="w-4 h-4" />,
        label: "Data Availability",
        value: `${dataCoverage.toFixed(0)}%`,
        subtext: `${coveredYears} of ${totalYears} years`,
        color: dataCoverage > 70 ? "text-emerald-400" : dataCoverage > 40 ? "text-amber-400" : "text-red-400",
    });

    // 5. Split impact (yield change at most recent split)
    if (epochs.length >= 2) {
        const preSplit = epochs[epochs.length - 2];
        const postSplit = epochs[epochs.length - 1];
        const preMetrics = (preSplit.metrics || []).filter((m: any) => m.collective_yield != null);
        const postMetrics = (postSplit.metrics || []).filter((m: any) => m.collective_yield != null);
        if (preMetrics.length > 0 && postMetrics.length > 0) {
            const preAvg = preMetrics.slice(-3).reduce((s: number, m: any) => s + m.collective_yield, 0) / Math.min(preMetrics.length, 3);
            const postAvg = postMetrics.slice(0, 3).reduce((s: number, m: any) => s + m.collective_yield, 0) / Math.min(postMetrics.length, 3);
            const impact = ((postAvg - preAvg) / preAvg) * 100;
            insights.push({
                icon: <Calendar className="w-4 h-4" />,
                label: "Last Split Impact",
                value: `${impact > 0 ? '+' : ''}${impact.toFixed(1)}%`,
                subtext: `at ${postSplit.year_start}`,
                color: Math.abs(impact) < 10 ? "text-amber-400" : impact > 0 ? "text-emerald-400" : "text-red-400",
            });
        }
    }

    return insights;
}

/* ---------- Group featured examples by state ---------- */
function groupByState(examples: SearchResult[]): Record<string, SearchResult[]> {
    return examples.reduce((acc, ex) => {
        if (!acc[ex.state]) acc[ex.state] = [];
        acc[ex.state].push(ex);
        return acc;
    }, {} as Record<string, SearchResult[]>);
}

export default function ReconstructorDashboard() {
    const mapRef = useRef<MapRef>(null);

    const [searchQuery, setSearchQuery] = useState("");
    const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [showResults, setShowResults] = useState(false);

    const [selectedCdk, setSelectedCdk] = useState("");
    const [selectedName, setSelectedName] = useState("");
    const [crop, setCrop] = useState("rice");
    
    const [epochs, setEpochs] = useState<any[]>([]);
    const [activeEpochIndex, setActiveEpochIndex] = useState<number>(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const grouped = useMemo(() => groupByState(FEATURED_EXAMPLES), []);
    const insights = useMemo(() => computeInsights(epochs, crop), [epochs, crop]);

    // Debounced search
    useEffect(() => {
        if (searchQuery.length < 2) { setSearchResults([]); return; }
        const delay = setTimeout(async () => {
            setIsSearching(true);
            try {
                const res = await fetch(`${API_URL}/api/v1/reconstruct/search?q=${encodeURIComponent(searchQuery)}`);
                if (res.ok) setSearchResults(await res.json());
            } catch { /* ignore */ } finally { setIsSearching(false); }
        }, 400);
        return () => clearTimeout(delay);
    }, [searchQuery]);

    const handleSelectResult = (cdk: string, name: string) => {
        setSelectedCdk(cdk);
        setSelectedName(name);
        setSearchQuery(name);
        setShowResults(false);
        runReconstruction(cdk);
    };

    const runReconstruction = async (cdk: string) => {
        if (!cdk) return;
        setError(""); setLoading(true);
        try {
            const res = await fetch(`${API_URL}/api/v1/reconstruct/${cdk}?crop=${crop}`);
            if (!res.ok) {
                const errBody = await res.json().catch(() => null);
                throw new Error(errBody?.detail || `Server ${res.status}`);
            }
            const data = await res.json();
            setEpochs(data.epochs || []); setActiveEpochIndex(0);
        } catch (err: any) {
            setError(err.message || "Failed to fetch");
        } finally { setLoading(false); }
    };

    // Arrow key navigation
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (epochs.length > 0) {
                if (e.key === "ArrowRight") setActiveEpochIndex(prev => Math.min(prev + 1, epochs.length - 1));
                else if (e.key === "ArrowLeft") setActiveEpochIndex(prev => Math.max(prev - 1, 0));
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [epochs]);

    const activeEpoch = epochs[activeEpochIndex];
    const CROPS = ["rice", "wheat", "maize", "bajra", "jowar", "sugarcane", "cotton"];

    return (
        <div className="flex flex-col h-full min-h-screen bg-slate-950 text-slate-100">
            
            {/* Compact Header */}
            <div className="px-6 py-4 bg-slate-900/80 backdrop-blur-xl border-b border-slate-800/50 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/20">
                        <Layers className="w-5 h-5 text-white" />
                    </div>
                    <div>
                        <h2 className="text-lg font-bold text-white tracking-tight">Lineage Reconstructor</h2>
                        <p className="text-xs text-slate-400">Reconstruct district boundaries across administrative changes</p>
                    </div>
                </div>
                {selectedName && (
                    <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-violet-500/10 border border-violet-500/20 rounded-lg">
                        <MapPin className="w-3.5 h-3.5 text-violet-400" />
                        <span className="text-sm font-medium text-violet-300">{selectedName}</span>
                    </div>
                )}
            </div>

            <div className="flex-1 p-4 lg:p-6 flex flex-col gap-5 max-w-[1600px] mx-auto w-full">
                
                {/* Search & Crop Row */}
                <div className="flex flex-col md:flex-row gap-3">
                    {/* Search */}
                    <div className="relative flex-1">
                        <div className="relative">
                            <Search className="absolute left-3.5 top-3 w-4.5 h-4.5 text-slate-500" />
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={(e) => { setSearchQuery(e.target.value); setShowResults(true); }}
                                onFocus={() => setShowResults(true)}
                                onBlur={() => setTimeout(() => setShowResults(false), 200)}
                                placeholder="Search districts — e.g. 24 Parganas, Meerut, Surat..."
                                className="w-full pl-11 pr-4 py-2.5 bg-slate-900/60 backdrop-blur border border-slate-700/50 rounded-xl text-sm text-slate-200 placeholder-slate-500 outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/40 transition-all"
                            />
                            {isSearching && <Loader2 className="absolute right-3.5 top-3 w-4.5 h-4.5 animate-spin text-slate-500" />}
                        </div>

                        {/* Dropdown */}
                        {showResults && (
                            <div className="absolute top-full left-0 w-full mt-1.5 bg-slate-900/95 backdrop-blur-xl border border-slate-700/50 rounded-xl shadow-2xl shadow-black/50 z-50 max-h-80 overflow-y-auto">
                                {searchQuery.length < 2 ? (
                                    <div className="py-2">
                                        <p className="px-4 py-2 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Featured Districts by State</p>
                                        {Object.entries(grouped).map(([state, districts]) => (
                                            <div key={state}>
                                                <p className="px-4 pt-2 pb-1 text-[10px] font-semibold text-violet-400/70 uppercase">{state}</p>
                                                {districts.map(r => (
                                                    <div 
                                                        key={r.cdk}
                                                        onClick={() => handleSelectResult(r.cdk, r.display_name)}
                                                        className="px-4 py-2 hover:bg-slate-800/60 cursor-pointer flex items-center justify-between group"
                                                    >
                                                        <span className="text-sm text-slate-300 group-hover:text-white transition">{r.display_name}</span>
                                                        <span className="text-[10px] text-slate-600 font-mono">{r.era}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        ))}
                                    </div>
                                ) : searchResults.length > 0 ? (
                                    searchResults.map(r => (
                                        <div 
                                            key={r.cdk}
                                            onClick={() => handleSelectResult(r.cdk, r.display_name)}
                                            className="px-4 py-3 hover:bg-slate-800/60 cursor-pointer flex items-center justify-between"
                                        >
                                            <div>
                                                <p className="text-sm font-medium text-slate-200">{r.display_name}</p>
                                                <p className="text-[10px] text-slate-500 font-mono mt-0.5">{r.cdk} • {r.state}</p>
                                            </div>
                                            <ChevronRight className="w-4 h-4 text-slate-600" />
                                        </div>
                                    ))
                                ) : !isSearching ? (
                                    <div className="p-4 text-sm text-slate-500">No districts found matching &quot;{searchQuery}&quot;</div>
                                ) : null}
                            </div>
                        )}
                    </div>

                    {/* Crop Pills */}
                    <div className="flex gap-1.5 items-center flex-wrap">
                        {CROPS.map(c => (
                            <button
                                key={c}
                                onClick={() => { setCrop(c); if (selectedCdk) runReconstruction(selectedCdk); }}
                                className={`px-3 py-2 rounded-lg text-xs font-medium transition-all capitalize
                                    ${crop === c 
                                        ? 'bg-violet-500/20 text-violet-300 border border-violet-500/30 shadow-sm shadow-violet-500/10' 
                                        : 'bg-slate-900/40 text-slate-500 border border-slate-800/50 hover:text-slate-300 hover:border-slate-700'}`}
                            >
                                {c}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Error */}
                {error && (
                    <div className="bg-red-500/10 text-red-400 px-4 py-3 rounded-xl border border-red-500/20 text-sm">{error}</div>
                )}

                {/* Loading */}
                {loading && (
                    <div className="flex justify-center items-center p-16">
                        <div className="flex items-center gap-3 bg-slate-900/80 backdrop-blur-xl px-6 py-3 rounded-full border border-slate-700/50 shadow-2xl">
                            <Loader2 className="w-5 h-5 animate-spin text-violet-400" />
                            <span className="text-slate-300 text-sm font-medium">Reconstructing lineage...</span>
                        </div>
                    </div>
                )}

                {/* Welcome State */}
                {epochs.length === 0 && !loading && !error && (
                    <div className="flex-1 flex items-center justify-center">
                        <div className="text-center max-w-md">
                            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-violet-500/20 to-indigo-500/20 border border-violet-500/10 flex items-center justify-center">
                                <GitBranch className="w-8 h-8 text-violet-400" />
                            </div>
                            <h3 className="text-lg font-semibold text-slate-200 mb-2">Select a District to Begin</h3>
                            <p className="text-sm text-slate-500 leading-relaxed">
                                Search or choose from {FEATURED_EXAMPLES.length} featured districts to visualize their complete administrative lineage and yield history.
                            </p>
                        </div>
                    </div>
                )}

                {/* Main Content */}
                {epochs.length > 0 && !loading && (
                    <div className="flex flex-col gap-5">
                        
                        {/* Map + Chart + Insights — 3-column */}
                        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5" style={{ minHeight: '480px' }}>
                            
                            {/* Map — 7 cols */}
                            <div className="lg:col-span-7 bg-slate-900/60 backdrop-blur border border-slate-800/50 rounded-2xl overflow-hidden relative shadow-xl shadow-black/20">
                                <Map
                                    ref={mapRef}
                                    initialViewState={{ longitude: 78.9629, latitude: 22.5, zoom: 4.2 }}
                                    mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
                                    style={{ width: "100%", height: "100%" }}
                                >
                                    <NavigationControl position="top-right" />
                                    
                                    {/* Base district boundaries (always visible) */}
                                    <Source id="all-districts" type="geojson" data="/data/districts.json">
                                        <Layer id="district-base-fill" type="fill" paint={{ "fill-color": "#1e293b", "fill-opacity": 0.4 }} />
                                        <Layer id="district-base-border" type="line" paint={{ "line-color": "#334155", "line-width": 0.5, "line-opacity": 0.6 }} />
                                    </Source>

                                    {/* India official boundary overlay */}
                                    <Source id="india-boundary" type="geojson" data="/data/india_boundary.json">
                                        <Layer id="india-boundary-line" type="line" paint={{ "line-color": "#6366f1", "line-width": 2, "line-opacity": 0.5 }} />
                                    </Source>

                                    {/* Reconstructed district geometry (if available) */}
                                    {activeEpoch && <ReconstructedMapLayer epoch={activeEpoch} />}
                                </Map>
                                {/* Map caption */}
                                <div className="absolute bottom-2 left-2 px-2 py-1 bg-slate-900/80 backdrop-blur rounded text-[9px] text-slate-500">
                                    Boundary: Survey of India (Official) • {641} Districts
                                </div>
                            </div>

                            {/* Right Panel: Chart + Insights — 5 cols */}
                            <div className="lg:col-span-5 flex flex-col gap-4">
                                
                                {/* Chart */}
                                <div className="bg-slate-900/60 backdrop-blur border border-slate-800/50 rounded-2xl p-5 flex-1 min-h-[280px]">
                                    <YieldReconstructionChart 
                                        epochs={epochs} 
                                        activeEpochIndex={activeEpochIndex} 
                                        onEpochChange={setActiveEpochIndex} 
                                    />
                                </div>

                                {/* Insights Strip */}
                                {insights.length > 0 && (
                                    <div className="grid grid-cols-2 xl:grid-cols-3 gap-2.5">
                                        {insights.map((ins, i) => (
                                            <div key={i} className="bg-slate-900/60 backdrop-blur border border-slate-800/50 rounded-xl px-3 py-2.5">
                                                <div className="flex items-center gap-1.5 mb-1">
                                                    <span className={ins.color}>{ins.icon}</span>
                                                    <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{ins.label}</span>
                                                </div>
                                                <p className="text-lg font-bold text-white leading-tight">{ins.value}</p>
                                                {ins.subtext && <p className="text-[10px] text-slate-500 mt-0.5">{ins.subtext}</p>}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Timeline */}
                        <EpochTimeline 
                            epochs={epochs} 
                            activeEpochIndex={activeEpochIndex} 
                            onEpochChange={setActiveEpochIndex} 
                        />

                        {/* Metrics Panel */}
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
