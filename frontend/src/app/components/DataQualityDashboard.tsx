"use client";

import React, { useState, useEffect } from "react";
import {
    Database, Shield, AlertTriangle, CheckCircle2, BarChart3,
    Loader2, RefreshCcw, Layers, Map, GitBranch, Zap
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface QualityData {
    districts: {
        total: number;
        with_geometry: number;
        geometry_coverage_pct: number;
    };
    split_events: {
        total: number;
        by_status: Record<string, number>;
        confidence_distribution: Record<string, number>;
    };
    transfers: {
        total: number;
        by_type: Array<{
            type: string;
            count: number;
            total_area_sqkm: number;
        }>;
    };
    enrichment: {
        total_rows: number;
        events_enriched: number;
    };
    geometry_sources: Record<string, number>;
}

const CONFIDENCE_COLORS: Record<string, string> = {
    high: "bg-emerald-500",
    medium: "bg-amber-500",
    low: "bg-red-500",
    none: "bg-slate-300",
};

const STATUS_COLORS: Record<string, string> = {
    complete: "text-emerald-600",
    partial: "text-amber-600",
    unknown: "text-slate-400",
};

function getErrorMessage(error: unknown): string {
    return error instanceof Error ? error.message : "Failed to load";
}

export default function DataQualityDashboard() {
    const [data, setData] = useState<QualityData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const fetchQuality = async () => {
        setLoading(true);
        setError("");
        try {
            const res = await fetch(`${API_URL}/api/v1/spatial/quality/overview`, {
                signal: AbortSignal.timeout(15000),
            });
            if (!res.ok) throw new Error("Failed to fetch quality data");
            const json = await res.json();
            setData(json);
        } catch (err: unknown) {
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchQuality(); }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-[60vh]">
                <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
                <p className="ml-3 text-slate-500 text-sm">Loading quality metrics…</p>
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="flex flex-col items-center justify-center h-[60vh] gap-3">
                <AlertTriangle className="w-10 h-10 text-amber-500" />
                <p className="text-slate-600">{error || "No data available"}</p>
                <button
                    onClick={fetchQuality}
                    className="px-4 py-2 bg-indigo-500 text-white rounded-lg text-sm hover:bg-indigo-600 transition-colors"
                >
                    Retry
                </button>
            </div>
        );
    }

    const totalConf = Object.values(data.split_events.confidence_distribution).reduce((a, b) => a + b, 0);

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-black text-slate-800 flex items-center gap-2">
                        <Database className="w-6 h-6 text-indigo-500" />
                        Data Quality Overview
                    </h1>
                    <p className="text-sm text-slate-400 mt-1">
                        Geometry coverage, split event confidence, and enrichment status
                    </p>
                </div>
                <button
                    onClick={fetchQuality}
                    className="flex items-center gap-2 px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-lg text-sm text-slate-600 transition-colors"
                >
                    <RefreshCcw className="w-4 h-4" /> Refresh
                </button>
            </div>

            {/* KPI Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <KpiCard
                    icon={<Map className="w-5 h-5 text-blue-500" />}
                    label="Geometry Coverage"
                    value={`${data.districts.geometry_coverage_pct}%`}
                    subtitle={`${data.districts.with_geometry} of ${data.districts.total} districts`}
                    color={data.districts.geometry_coverage_pct > 50 ? "border-blue-200" : "border-amber-200"}
                />
                <KpiCard
                    icon={<GitBranch className="w-5 h-5 text-purple-500" />}
                    label="Split Events"
                    value={data.split_events.total.toLocaleString()}
                    subtitle="Total recorded splits"
                    color="border-purple-200"
                />
                <KpiCard
                    icon={<Layers className="w-5 h-5 text-emerald-500" />}
                    label="Area Transfers"
                    value={data.transfers.total.toLocaleString()}
                    subtitle="Classified regions"
                    color="border-emerald-200"
                />
                <KpiCard
                    icon={<Zap className="w-5 h-5 text-amber-500" />}
                    label="Enrichment"
                    value={data.enrichment.total_rows.toLocaleString()}
                    subtitle={`${data.enrichment.events_enriched} events enriched`}
                    color="border-amber-200"
                />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Confidence Distribution */}
                <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
                    <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
                        <Shield className="w-4 h-4 text-indigo-500" />
                        Confidence Distribution
                    </h3>
                    {totalConf > 0 ? (
                        <>
                            <div className="flex h-4 rounded-full overflow-hidden bg-slate-100">
                                {Object.entries(data.split_events.confidence_distribution).map(([bucket, count]) => (
                                    <div
                                        key={bucket}
                                        className={`${CONFIDENCE_COLORS[bucket] || "bg-slate-300"} transition-all`}
                                        style={{ width: `${(count / totalConf) * 100}%` }}
                                        title={`${bucket}: ${count}`}
                                    />
                                ))}
                            </div>
                            <div className="flex gap-4 text-xs">
                                {Object.entries(data.split_events.confidence_distribution).map(([bucket, count]) => (
                                    <div key={bucket} className="flex items-center gap-1.5">
                                        <div className={`w-2.5 h-2.5 rounded-full ${CONFIDENCE_COLORS[bucket]}`} />
                                        <span className="text-slate-500 capitalize">{bucket}</span>
                                        <span className="text-slate-700 font-bold">{count}</span>
                                    </div>
                                ))}
                            </div>
                        </>
                    ) : (
                        <p className="text-xs text-slate-400 italic">No split events with confidence scores yet.</p>
                    )}
                </div>

                {/* Geometry Status */}
                <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
                    <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-blue-500" />
                        Events by Geometry Status
                    </h3>
                    <div className="space-y-2">
                        {Object.entries(data.split_events.by_status).map(([status, count]) => (
                            <div key={status} className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <CheckCircle2 className={`w-4 h-4 ${STATUS_COLORS[status] || "text-slate-400"}`} />
                                    <span className="text-sm text-slate-600 capitalize">{status}</span>
                                </div>
                                <span className="text-sm font-bold text-slate-700">{count}</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Transfer Types */}
                <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
                    <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
                        <Layers className="w-4 h-4 text-emerald-500" />
                        Transfer Type Breakdown
                    </h3>
                    <div className="space-y-2">
                        {data.transfers.by_type.map((t) => (
                            <div key={t.type} className="flex items-center justify-between bg-slate-50 rounded-lg p-3">
                                <span className="text-sm text-slate-600 capitalize font-medium">
                                    {t.type.replace(/_/g, " ")}
                                </span>
                                <div className="text-right">
                                    <span className="text-sm font-bold text-slate-700">{t.count}</span>
                                    <p className="text-[10px] text-slate-400">
                                        {t.total_area_sqkm.toLocaleString(undefined, { maximumFractionDigits: 1 })} km²
                                    </p>
                                </div>
                            </div>
                        ))}
                        {data.transfers.by_type.length === 0 && (
                            <p className="text-xs text-slate-400 italic">No transfers computed yet.</p>
                        )}
                    </div>
                </div>

                {/* Geometry Sources */}
                <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
                    <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
                        <Map className="w-4 h-4 text-blue-500" />
                        Geometry Sources
                    </h3>
                    <div className="space-y-2">
                        {Object.entries(data.geometry_sources).map(([source, count]) => (
                            <div key={source} className="flex items-center justify-between bg-slate-50 rounded-lg p-3">
                                <span className="text-sm text-slate-600 capitalize font-medium">
                                    {source.replace(/_/g, " ")}
                                </span>
                                <span className="text-sm font-bold text-slate-700">{count}</span>
                            </div>
                        ))}
                        {Object.keys(data.geometry_sources).length === 0 && (
                            <p className="text-xs text-slate-400 italic">No geometry uploads yet.</p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

function KpiCard({
    icon,
    label,
    value,
    subtitle,
    color,
}: {
    icon: React.ReactNode;
    label: string;
    value: string;
    subtitle: string;
    color: string;
}) {
    return (
        <div className={`bg-white rounded-xl border-2 ${color} p-4 space-y-2`}>
            <div className="flex items-center gap-2">
                {icon}
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wide">{label}</span>
            </div>
            <p className="text-2xl font-black text-slate-800">{value}</p>
            <p className="text-xs text-slate-400">{subtitle}</p>
        </div>
    );
}
