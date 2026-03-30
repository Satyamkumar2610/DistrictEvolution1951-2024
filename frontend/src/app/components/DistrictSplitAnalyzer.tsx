"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";
import Map, { Source, Layer, MapRef } from "react-map-gl/maplibre";
import * as turf from "@turf/turf";
import {
    UploadCloud, Loader2, AlertCircle, FileJson, Plus, Trash2,
    Shield, ArrowRight, CheckCircle2, AlertTriangle, Download,
    Database, MapPin, GraduationCap, HeartPulse, Compass
} from "lucide-react";
import "maplibre-gl/dist/maplibre-gl.css";
import { FeatureCollection, Geometry } from "geojson";
import { buildPublicApiV1Url } from "../services/api/config";

// ── Types ────────────────────────────────────────────────────────────────

interface TransferDetail {
    from_district: string;
    to_district: string;
    transfer_type: string;
    area_sqkm: number;
    confidence_score: number;
}

interface DiffResponse {
    success: boolean;
    event_id: number | null;
    parent_cdk: string;
    child_cdks: string[];
    split_year: number;
    parent_area_sqkm: number;
    total_child_area_sqkm: number;
    area_conservation_error: number;
    composite_confidence: number;
    geometry_status: string;
    transfers: TransferDetail[];
    warnings: string[];
    geojson: FeatureCollection<Geometry>;
}

interface UploadResponse {
    success: boolean;
    district_cdk: string;
    snapshot_year: number;
    geometry_source: string;
    geometry_confidence: number;
    area_sqkm: number | null;
    message: string;
}

interface EnrichmentMetric {
    dataset: string;
    metric: string;
    value: number | null;
    unit: string | null;
    reference_year: number | null;
    source_url: string | null;
}

interface EnrichmentTransfer {
    transfer_id: number;
    from_district: string;
    to_district: string;
    transfer_type: string;
    transfer_area_sqkm: number;
    metrics: EnrichmentMetric[];
}

interface EnrichmentResponse {
    success: boolean;
    event_id: number;
    parent_cdk: string;
    split_year: number;
    total_enrichment_rows: number;
    transfers: EnrichmentTransfer[];
}

interface ChildEntry {
    id: string;
    cdk: string;
    file: File | null;
    geojson: FeatureCollection<Geometry> | null;
    uploaded: boolean;
}

type AnalysisState = "idle" | "uploading" | "processing" | "success" | "error";

// ── Color Palette ────────────────────────────────────────────────────────

const TRANSFER_COLORS: Record<string, { fill: string; line: string; label: string }> = {
    inherited: { fill: "#10b981", line: "#059669", label: "Inherited" },
    transferred_in: { fill: "#3b82f6", line: "#2563eb", label: "Transferred In" },
    transferred_out: { fill: "#f97316", line: "#ea580c", label: "Transferred Out" },
    overlap: { fill: "#ef4444", line: "#dc2626", label: "Overlap (Error)" },
    gap: { fill: "#eab308", line: "#ca8a04", label: "Gap (Unaccounted)" },
};

// ── Helpers ──────────────────────────────────────────────────────────────

function generateId() {
    return Math.random().toString(36).slice(2, 9);
}

function confidenceBadge(score: number) {
    if (score >= 0.85) return { color: "text-emerald-600 bg-emerald-50 border-emerald-200", label: "High" };
    if (score >= 0.6) return { color: "text-amber-600 bg-amber-50 border-amber-200", label: "Medium" };
    return { color: "text-rose-600 bg-rose-50 border-rose-200", label: "Low" };
}

function statusBadge(status: string) {
    if (status === "complete") return { color: "text-emerald-700 bg-emerald-50", icon: CheckCircle2 };
    if (status === "partial") return { color: "text-amber-700 bg-amber-50", icon: AlertTriangle };
    return { color: "text-rose-700 bg-rose-50", icon: AlertCircle };
}

function getErrorMessage(error: unknown, fallback: string): string {
    return error instanceof Error ? error.message : fallback;
}

// ── Main Component ───────────────────────────────────────────────────────

export default function DistrictSplitAnalyzer() {
    const mapRef = useRef<MapRef>(null);

    // Parent state
    const [parentCdk, setParentCdk] = useState("");
    const [parentFile, setParentFile] = useState<File | null>(null);
    const [parentGeoJson, setParentGeoJson] = useState<FeatureCollection<Geometry> | null>(null);
    const [parentUploaded, setParentUploaded] = useState(false);

    // Children state
    const [children, setChildren] = useState<ChildEntry[]>([
        { id: generateId(), cdk: "", file: null, geojson: null, uploaded: false },
    ]);

    // Split year
    const [splitYear, setSplitYear] = useState(2024);

    // Results
    const [result, setResult] = useState<DiffResponse | null>(null);
    const [enrichment, setEnrichment] = useState<EnrichmentResponse | null>(null);
    const [enrichmentLoading, setEnrichmentLoading] = useState(false);
    const [status, setStatus] = useState<AnalysisState>("idle");
    const [errorMessage, setErrorMessage] = useState("");
    const [eventId, setEventId] = useState<number | null>(null);

    const [viewState, setViewState] = useState({
        longitude: 78.9629,
        latitude: 20.5937,
        zoom: 4,
    });

    // Auto-poll enrichment data after diff completes
    useEffect(() => {
        if (!eventId || status !== "success") return;
        let cancelled = false;
        let attempts = 0;
        const maxAttempts = 10;

        const poll = async () => {
            setEnrichmentLoading(true);
            while (!cancelled && attempts < maxAttempts) {
                attempts++;
                try {
                    const res = await fetch(buildPublicApiV1Url(`/spatial/enrichment/${eventId}`), {
                        signal: AbortSignal.timeout(10000),
                    });
                    if (res.ok) {
                        const data: EnrichmentResponse = await res.json();
                        if (data.total_enrichment_rows > 0) {
                            setEnrichment(data);
                            setEnrichmentLoading(false);
                            return;
                        }
                    }
                } catch { /* retry */ }
                // Wait 3 seconds before retry
                await new Promise(r => setTimeout(r, 3000));
            }
            setEnrichmentLoading(false);
        };
        poll();
        return () => { cancelled = true; };
    }, [eventId, status]);

    // ── File Handling ────────────────────────────────────────────────────

    const handleFile = useCallback(async (
        file: File,
        setGeoJson: (gj: FeatureCollection<Geometry>) => void,
    ) => {
        const text = await file.text();
        const geojson = JSON.parse(text);
        let normalized: FeatureCollection<Geometry>;

        if (geojson.type === "FeatureCollection") {
            normalized = geojson;
        } else if (geojson.type === "Feature") {
            normalized = turf.featureCollection([geojson]);
        } else if (geojson.type === "Polygon" || geojson.type === "MultiPolygon") {
            normalized = turf.featureCollection([turf.feature(geojson)]);
        } else {
            throw new Error("Invalid GeoJSON format.");
        }

        setGeoJson(normalized);

        if (mapRef.current) {
            const bbox = turf.bbox(normalized);
            mapRef.current.fitBounds(
                [[bbox[0], bbox[1]], [bbox[2], bbox[3]]],
                { padding: 50, duration: 800 }
            );
        }
    }, []);

    const handleParentFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setParentFile(file);
        setParentUploaded(false);
        try {
            await handleFile(file, setParentGeoJson);
        } catch (err: unknown) {
            setErrorMessage(`Parent file error: ${getErrorMessage(err, "Invalid file")}`);
            setStatus("error");
        }
    };

    const handleChildFile = async (childId: string, e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        try {
            let parsedGj: FeatureCollection<Geometry> | null = null;
            await handleFile(file, (gj) => { parsedGj = gj; });
            setChildren(prev => prev.map(c =>
                c.id === childId ? { ...c, file, geojson: parsedGj, uploaded: false } : c
            ));
        } catch (err: unknown) {
            setErrorMessage(`Child file error: ${getErrorMessage(err, "Invalid file")}`);
            setStatus("error");
        }
    };

    const addChild = () => {
        setChildren(prev => [...prev, { id: generateId(), cdk: "", file: null, geojson: null, uploaded: false }]);
    };

    const removeChild = (id: string) => {
        setChildren(prev => prev.filter(c => c.id !== id));
    };

    const updateChildCdk = (id: string, cdk: string) => {
        setChildren(prev => prev.map(c => c.id === id ? { ...c, cdk } : c));
    };

    // ── Upload to Backend ────────────────────────────────────────────────

    const uploadGeometry = async (cdk: string, year: number, geojson: FeatureCollection<Geometry>): Promise<UploadResponse> => {
        const res = await fetch(buildPublicApiV1Url("/spatial/upload-geojson"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                district_cdk: cdk,
                snapshot_year: year,
                geojson: geojson.features[0]?.geometry || geojson,
            }),
            signal: AbortSignal.timeout(30000),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: "Upload failed" }));
            throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
        }
        return res.json();
    };

    // ── Main Analysis Flow ───────────────────────────────────────────────

    const runAnalysis = async () => {
        setErrorMessage("");
        setResult(null);
        setEnrichment(null);
        setEventId(null);

        // Validation
        if (!parentCdk.trim()) { setErrorMessage("Enter Parent CDK"); setStatus("error"); return; }
        if (!parentGeoJson) { setErrorMessage("Upload parent boundary"); setStatus("error"); return; }

        const validChildren = children.filter(c => c.cdk.trim() && c.geojson);
        if (validChildren.length === 0) {
            setErrorMessage("Add at least one child with CDK and boundary file");
            setStatus("error");
            return;
        }

        try {
            // Step 1: Upload geometries
            setStatus("uploading");

            if (!parentUploaded) {
                await uploadGeometry(parentCdk, splitYear, parentGeoJson);
                setParentUploaded(true);
            }

            for (const child of validChildren) {
                if (!child.uploaded && child.geojson) {
                    await uploadGeometry(child.cdk, splitYear, child.geojson);
                    setChildren(prev => prev.map(c =>
                        c.id === child.id ? { ...c, uploaded: true } : c
                    ));
                }
            }

            // Step 2: Run diff
            setStatus("processing");

            const diffRes = await fetch(buildPublicApiV1Url("/spatial/diff"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    parent_cdk: parentCdk,
                    child_cdks: validChildren.map(c => c.cdk),
                    split_year: splitYear,
                }),
                signal: AbortSignal.timeout(60000),
            });

            if (!diffRes.ok) {
                const err = await diffRes.json().catch(() => ({ detail: "Diff failed" }));
                throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
            }

            const data: DiffResponse = await diffRes.json();
            setResult(data);
            setStatus("success");

            // Use event_id from the backend response for enrichment polling
            if (data.event_id) {
                setEventId(data.event_id);
            }

            // Zoom to results
            if (data.geojson?.features?.length && mapRef.current) {
                const bbox = turf.bbox(data.geojson);
                mapRef.current.fitBounds(
                    [[bbox[0], bbox[1]], [bbox[2], bbox[3]]],
                    { padding: 60, duration: 1000 }
                );
            }

        } catch (err: unknown) {
            console.error(err);
            setErrorMessage(getErrorMessage(err, "Analysis failed"));
            setStatus("error");
        }
    };

    // ── Export GeoJSON ────────────────────────────────────────────────────

    const exportResults = () => {
        if (!result?.geojson) return;
        const blob = new Blob([JSON.stringify(result.geojson, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `split_diff_${parentCdk}_${splitYear}.geojson`;
        a.click();
        URL.revokeObjectURL(url);
    };

    // ── Render ───────────────────────────────────────────────────────────

    const badge = result ? confidenceBadge(result.composite_confidence) : null;
    const stBadge = result ? statusBadge(result.geometry_status) : null;

    return (
        <div className="flex flex-col h-full bg-white rounded-xl shadow-xl overflow-hidden border border-slate-200">

            {/* ─── Header ──────────────────────────────────────────────── */}
            <div className="px-6 py-5 border-b border-slate-200 bg-gradient-to-r from-indigo-50 to-slate-50">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                            <Shield className="w-6 h-6 text-indigo-500" />
                            District Split Analyzer
                        </h2>
                        <p className="text-slate-500 mt-1 text-sm">
                            Upload parent &amp; child boundaries → PostGIS computes inherited, transferred, gap, and overlap regions.
                        </p>
                    </div>
                    {result && (
                        <button
                            onClick={exportResults}
                            className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition shadow-sm"
                        >
                            <Download className="w-4 h-4" /> Export GeoJSON
                        </button>
                    )}
                </div>
            </div>

            <div className="flex flex-1 flex-col lg:flex-row overflow-hidden">

                {/* ─── Left Panel ──────────────────────────────────────── */}
                <div className="w-full lg:w-[380px] p-5 flex flex-col gap-5 overflow-y-auto border-r border-slate-200 bg-slate-50/50">

                    {/* Error */}
                    {status === "error" && (
                        <div className="p-3 bg-red-50 text-red-700 rounded-lg flex items-start gap-2 text-sm border border-red-200">
                            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                            <p>{errorMessage}</p>
                        </div>
                    )}

                    {/* Split Year */}
                    <div>
                        <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Split Year</label>
                        <input
                            type="number"
                            value={splitYear}
                            onChange={(e) => setSplitYear(Number(e.target.value))}
                            min={1950}
                            max={2030}
                            className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 outline-none"
                        />
                    </div>

                    {/* Parent */}
                    <div className="space-y-2">
                        <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider">Parent District</label>
                        <input
                            type="text"
                            value={parentCdk}
                            onChange={(e) => setParentCdk(e.target.value)}
                            placeholder="e.g. TG_adilab_2011"
                            className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 outline-none"
                        />
                        <label className="flex items-center justify-center w-full h-20 border-2 border-dashed border-slate-300 rounded-lg cursor-pointer bg-white hover:bg-slate-50 transition">
                            <div className="flex items-center gap-2 text-sm text-slate-500">
                                {parentFile ? (
                                    <><FileJson className="w-5 h-5 text-emerald-500" /><span className="font-medium truncate max-w-[200px]">{parentFile.name}</span></>
                                ) : (
                                    <><UploadCloud className="w-5 h-5" /><span>Upload GeoJSON</span></>
                                )}
                            </div>
                            <input type="file" className="hidden" accept=".geojson,.json" onChange={handleParentFile} />
                        </label>
                    </div>

                    {/* Children */}
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider">Child Districts</label>
                            <button
                                onClick={addChild}
                                className="flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-800 transition"
                            >
                                <Plus className="w-3.5 h-3.5" /> Add Child
                            </button>
                        </div>

                        {children.map((child, i) => (
                            <div key={child.id} className="bg-white rounded-lg border border-slate-200 p-3 space-y-2">
                                <div className="flex items-center gap-2">
                                    <span className="text-xs font-bold text-slate-400 w-4">{i + 1}.</span>
                                    <input
                                        type="text"
                                        value={child.cdk}
                                        onChange={(e) => updateChildCdk(child.id, e.target.value)}
                                        placeholder="e.g. TG_nirmal_2024"
                                        className="flex-1 px-2 py-1.5 bg-slate-50 border border-slate-200 rounded text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 outline-none"
                                    />
                                    {children.length > 1 && (
                                        <button onClick={() => removeChild(child.id)} className="text-slate-400 hover:text-rose-500 transition">
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    )}
                                </div>
                                <label className="flex items-center justify-center w-full h-14 border border-dashed border-slate-300 rounded cursor-pointer bg-slate-50 hover:bg-white transition text-sm text-slate-500">
                                    {child.file ? (
                                        <span className="flex items-center gap-1"><FileJson className="w-4 h-4 text-blue-500" /><span className="truncate max-w-[180px]">{child.file.name}</span></span>
                                    ) : (
                                        <span className="flex items-center gap-1"><UploadCloud className="w-4 h-4" />Upload GeoJSON</span>
                                    )}
                                    <input type="file" className="hidden" accept=".geojson,.json" onChange={(e) => handleChildFile(child.id, e)} />
                                </label>
                            </div>
                        ))}
                    </div>

                    {/* Analyze Button */}
                    <button
                        onClick={runAnalysis}
                        disabled={status === "uploading" || status === "processing"}
                        className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-semibold rounded-lg shadow-sm transition flex items-center justify-center gap-2 disabled:cursor-not-allowed"
                    >
                        {status === "uploading" ? (
                            <><Loader2 className="w-5 h-5 animate-spin" /> Uploading Geometries…</>
                        ) : status === "processing" ? (
                            <><Loader2 className="w-5 h-5 animate-spin" /> Running PostGIS Diff…</>
                        ) : (
                            <><ArrowRight className="w-5 h-5" /> Analyze Split</>
                        )}
                    </button>

                    {/* ─── Results Summary ─────────────────────────────── */}
                    {result && (
                        <div className="space-y-4">
                            {/* Confidence + Status */}
                            <div className="flex items-center gap-2">
                                {stBadge && (
                                    <span className={`px-2 py-1 rounded-md text-xs font-bold ${stBadge.color} flex items-center gap-1`}>
                                        <stBadge.icon className="w-3 h-3" /> {result.geometry_status}
                                    </span>
                                )}
                                {badge && (
                                    <span className={`px-2 py-1 rounded-md text-xs font-bold border ${badge.color}`}>
                                        Confidence: {(result.composite_confidence * 100).toFixed(1)}%
                                    </span>
                                )}
                            </div>

                            {/* Area Stats */}
                            <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
                                <h3 className="text-sm font-bold text-slate-700">Area Summary</h3>
                                <div className="grid grid-cols-2 gap-3">
                                    <div className="bg-slate-50 rounded-lg p-3">
                                        <p className="text-[10px] font-bold text-slate-400 uppercase">Parent Area</p>
                                        <p className="text-lg font-black text-slate-900">{result.parent_area_sqkm.toLocaleString(undefined, { maximumFractionDigits: 1 })}</p>
                                        <p className="text-[10px] text-slate-400">sq km</p>
                                    </div>
                                    <div className="bg-slate-50 rounded-lg p-3">
                                        <p className="text-[10px] font-bold text-slate-400 uppercase">Children Total</p>
                                        <p className="text-lg font-black text-slate-900">{result.total_child_area_sqkm.toLocaleString(undefined, { maximumFractionDigits: 1 })}</p>
                                        <p className="text-[10px] text-slate-400">sq km</p>
                                    </div>
                                </div>
                                <div className="bg-slate-50 rounded-lg p-3">
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Conservation Error</p>
                                    <p className={`text-lg font-black ${result.area_conservation_error > 0.05 ? "text-amber-600" : "text-emerald-600"}`}>
                                        {(result.area_conservation_error * 100).toFixed(2)}%
                                    </p>
                                </div>
                            </div>

                            {/* Transfers */}
                            <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
                                <h3 className="text-sm font-bold text-slate-700">Classified Transfers</h3>
                                <div className="space-y-2 max-h-[300px] overflow-y-auto">
                                    {result.transfers.map((t, i) => {
                                        const tc = TRANSFER_COLORS[t.transfer_type] || TRANSFER_COLORS.inherited;
                                        return (
                                            <div key={i} className="flex items-center gap-3 p-2 bg-slate-50 rounded-lg">
                                                <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: tc.fill, border: `2px solid ${tc.line}` }} />
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-xs font-bold text-slate-700 truncate">{t.from_district} → {t.to_district}</p>
                                                    <p className="text-[10px] text-slate-400">{tc.label} · {t.area_sqkm.toLocaleString(undefined, { maximumFractionDigits: 2 })} sq km</p>
                                                </div>
                                                <span className="text-[10px] font-bold text-slate-400">{(t.confidence_score * 100).toFixed(0)}%</span>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* Warnings */}
                            {result.warnings.length > 0 && (
                                <div className="bg-amber-50 rounded-xl border border-amber-200 p-4">
                                    <h3 className="text-sm font-bold text-amber-700 mb-2 flex items-center gap-1">
                                        <AlertTriangle className="w-4 h-4" /> Warnings
                                    </h3>
                                    <ul className="space-y-1">
                                        {result.warnings.map((w, i) => (
                                            <li key={i} className="text-xs text-amber-600">{w}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* Enrichment Insights */}
                            <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
                                <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
                                    <Database className="w-4 h-4 text-indigo-500" />
                                    Enrichment Insights
                                    {enrichmentLoading && (
                                        <span className="flex items-center gap-1 text-[10px] font-normal text-indigo-400">
                                            <Loader2 className="w-3 h-3 animate-spin" /> Loading…
                                        </span>
                                    )}
                                </h3>

                                {enrichment && enrichment.transfers.length > 0 ? (
                                    <div className="space-y-3 max-h-[300px] overflow-y-auto">
                                        {enrichment.transfers.map((et) => (
                                            <div key={et.transfer_id} className="bg-slate-50 rounded-lg p-3 space-y-2">
                                                <p className="text-xs font-bold text-slate-600">
                                                    {et.from_district} → {et.to_district}
                                                    <span className="ml-2 text-slate-400 font-normal">{et.transfer_type}</span>
                                                </p>
                                                <div className="grid grid-cols-2 gap-2">
                                                    {et.metrics.map((m, j) => {
                                                        const icon = m.metric.includes("settlement") ? MapPin
                                                            : m.metric.includes("school") ? GraduationCap
                                                            : m.metric.includes("hospital") ? HeartPulse
                                                            : m.metric.includes("centroid") ? Compass
                                                            : Database;
                                                        const Icon = icon;
                                                        return (
                                                            <div key={j} className="flex items-center gap-1.5 text-[11px]">
                                                                <Icon className="w-3 h-3 text-slate-400 flex-shrink-0" />
                                                                <span className="text-slate-500 truncate">{m.metric.replace(/_/g, " ")}</span>
                                                                <span className="ml-auto font-bold text-slate-700">
                                                                    {m.value !== null ? m.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "—"}
                                                                </span>
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : !enrichmentLoading ? (
                                    <p className="text-xs text-slate-400 italic">Enrichment data will appear here after analysis. Background workers are processing OSM, agricultural, and geometric metrics.</p>
                                ) : null}
                            </div>
                        </div>
                    )}
                </div>

                {/* ─── Map ─────────────────────────────────────────────── */}
                <div className="flex-1 w-full bg-slate-100 relative min-h-[400px]">
                    <Map
                        ref={mapRef}
                        id="split-map-v2"
                        initialViewState={viewState}
                        onMove={(evt) => setViewState(evt.viewState)}
                        mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
                        style={{ width: "100%", height: "100%" }}
                    >
                        {/* Pre-analysis: show uploaded parent */}
                        {parentGeoJson && !result && (
                            <Source id="pre-parent" type="geojson" data={parentGeoJson}>
                                <Layer id="pre-parent-fill" type="fill" paint={{ "fill-color": "#94a3b8", "fill-opacity": 0.25 }} />
                                <Layer id="pre-parent-line" type="line" paint={{ "line-color": "#475569", "line-width": 2, "line-dasharray": [3, 2] }} />
                            </Source>
                        )}

                        {/* Pre-analysis: show uploaded children */}
                        {!result && children.map((child) =>
                            child.geojson ? (
                                <Source key={`pre-child-${child.id}`} id={`pre-child-${child.id}`} type="geojson" data={child.geojson}>
                                    <Layer id={`pre-child-fill-${child.id}`} type="fill" paint={{ "fill-color": "#60a5fa", "fill-opacity": 0.3 }} />
                                    <Layer id={`pre-child-line-${child.id}`} type="line" paint={{ "line-color": "#2563eb", "line-width": 1.5 }} />
                                </Source>
                            ) : null
                        )}

                        {/* Post-analysis: diff result layers */}
                        {result?.geojson?.features && (
                            <>
                                {Object.keys(TRANSFER_COLORS).map(ttype => {
                                    const features = result.geojson.features.filter(
                                        (f) => f.properties?.transfer_type === ttype
                                    );
                                    if (!features.length) return null;
                                    const fc = { type: "FeatureCollection" as const, features };
                                    const tc = TRANSFER_COLORS[ttype];
                                    return (
                                        <Source key={`result-${ttype}`} id={`result-${ttype}`} type="geojson" data={fc}>
                                            <Layer
                                                id={`result-fill-${ttype}`}
                                                type="fill"
                                                paint={{ "fill-color": tc.fill, "fill-opacity": 0.55 }}
                                            />
                                            <Layer
                                                id={`result-line-${ttype}`}
                                                type="line"
                                                paint={{ "line-color": tc.line, "line-width": 2 }}
                                            />
                                        </Source>
                                    );
                                })}
                            </>
                        )}
                    </Map>

                    {/* Legend */}
                    {result && (
                        <div className="absolute bottom-4 left-4 py-3 px-4 rounded-xl bg-white/95 shadow-lg backdrop-blur-sm border border-slate-200">
                            <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Legend</h4>
                            <div className="space-y-1.5">
                                {Object.entries(TRANSFER_COLORS).map(([key, val]) => {
                                    const count = result.transfers.filter(t => t.transfer_type === key).length;
                                    if (count === 0) return null;
                                    return (
                                        <div key={key} className="flex items-center gap-2">
                                            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: val.fill, border: `2px solid ${val.line}` }} />
                                            <span className="text-xs text-slate-600">{val.label} ({count})</span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
