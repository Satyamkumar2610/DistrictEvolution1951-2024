'use client';

import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import { ApiError } from '../../services/api/client';
import { AINarrative } from '../../components/AINarrative';
import {
    History, GitBranch, AlertTriangle, Info, TrendingUp,
    ShieldCheck, ShieldAlert, Cpu, ChevronDown, ChevronUp
} from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import type { BackcastResponse, BackcastChildResult, SplitDistrict } from '../../services/api/types';

/* ────────────────────────────────────────────────────────────────────────── */
/*  PALETTE — assign a unique colour to each child district                 */
/* ────────────────────────────────────────────────────────────────────────── */
const CHILD_COLORS = [
    '#6366f1', // indigo-500
    '#f59e0b', // amber-500
    '#10b981', // emerald-500
    '#ef4444', // rose-500
    '#8b5cf6', // violet-500
    '#06b6d4', // cyan-500
    '#ec4899', // pink-500
    '#84cc16', // lime-500
];

const BAND_OPACITY = 0.12;

/* ────────────────────────────────────────────────────────────────────────── */
/*  HELPER — normalise CDK strings for display                              */
/* ────────────────────────────────────────────────────────────────────────── */
function cdkLabel(cdk: string) {
    // Turn "TN_chenna_2024" into "Chennai (2024)"
    const parts = cdk.split('_');
    if (parts.length >= 3) {
        const name = parts.slice(1, -1).map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(' ');
        return `${name} (${parts[parts.length - 1]})`;
    }
    return cdk;
}

function methodBadge(method: string) {
    const m = method.toLowerCase();
    if (m.includes('gradient') || m.includes('ml')) return { label: 'ML (GBM)', cls: 'bg-emerald-100 text-emerald-700 border-emerald-200' };
    if (m.includes('ridge')) return { label: 'Ridge', cls: 'bg-sky-100 text-sky-700 border-sky-200' };
    if (m.includes('ratio')) return { label: 'Ratio', cls: 'bg-amber-100 text-amber-700 border-amber-200' };
    if (m.includes('apportionment') || m.includes('apportion')) return { label: 'Apportioned', cls: 'bg-slate-100 text-slate-700 border-slate-200' };
    return { label: method, cls: 'bg-slate-100 text-slate-700 border-slate-200' };
}

/* ────────────────────────────────────────────────────────────────────────── */
/*  PAGE COMPONENT                                                          */
/* ────────────────────────────────────────────────────────────────────────── */
export default function BackcastPage() {
    /* ── state ───────────────────────────────────────────────────────────── */
    const [selectedState, setSelectedState] = useState('');
    const [selectedEventIdx, setSelectedEventIdx] = useState(-1);
    const [selectedCrop, setSelectedCrop] = useState('rice');
    const [startYear, setStartYear] = useState(1966);
    const [expandedChild, setExpandedChild] = useState<string | null>(null);

    /* ── data: states list ───────────────────────────────────────────────── */
    const { data: summaryData } = useQuery({
        queryKey: ['stateSummary'],
        queryFn: api.getSummary,
        staleTime: 3600000,
    });
    const states = useMemo(() => {
        if (!summaryData?.states) return [];
        return (Array.isArray(summaryData.states) ? summaryData.states : Object.keys(summaryData.states)).sort();
    }, [summaryData]);

    /* ── data: split events for selected state ───────────────────────────── */
    const { data: splitEvents } = useQuery({
        queryKey: ['splitEvents', selectedState],
        queryFn: () => api.getSplitEvents(selectedState),
        enabled: !!selectedState,
        staleTime: 600_000,
    });

    /* derive the selected event object */
    const selectedEvent: SplitDistrict | null = useMemo(() => {
        if (!splitEvents || selectedEventIdx < 0) return null;
        return splitEvents[selectedEventIdx] ?? null;
    }, [splitEvents, selectedEventIdx]);

    /* ── data: backcast query ────────────────────────────────────────────── */
    const canQuery = !!selectedEvent?.parent_cdk && (selectedEvent?.children_cdks?.filter(Boolean).length ?? 0) > 0;

    const { data, isLoading, isError, error } = useQuery({
        queryKey: [
            'backcast',
            selectedEvent?.parent_cdk,
            selectedEvent?.children_cdks,
            selectedEvent?.split_year,
            selectedCrop,
            startYear,
        ],
        queryFn: () => api.getBackcast(
            selectedEvent!.parent_cdk!,
            selectedEvent!.children_cdks.filter(Boolean) as string[],
            selectedEvent!.split_year,
            selectedCrop,
            startYear,
        ),
        enabled: canQuery,
        staleTime: 300_000,
        retry: 1,
    });

    const apiError = error instanceof ApiError ? error : null;
    const isNoDataError = !!apiError && [400, 404, 422].includes(apiError.status);
    const hasData = !!data && Object.keys(data.children).length > 0;

    /* ── chart option ────────────────────────────────────────────────────── */
    const chartOption = useMemo(() => {
        if (!hasData || !data) return null;

        const childEntries = Object.entries(data.children);
        // Collect all years across all children
        const allYears = new Set<number>();
        childEntries.forEach(([, child]) => {
            child.backcasted_yields.forEach(p => allYears.add(p.year));
        });
        const years = [...allYears].sort((a, b) => a - b);

        const series: Record<string, unknown>[] = [];

        childEntries.forEach(([cdk, child], idx) => {
            const color = CHILD_COLORS[idx % CHILD_COLORS.length];
            const label = cdkLabel(cdk);

            // upper bound (invisible line to anchor band)
            const upperData = years.map(y => {
                const pt = child.backcasted_yields.find(p => p.year === y);
                return pt ? pt.upper_bound : null;
            });
            series.push({
                name: `${label} upper`,
                type: 'line',
                data: upperData,
                lineStyle: { opacity: 0 },
                symbol: 'none',
                stack: `ci-${idx}`,
                silent: true,
                z: 1,
            });

            // confidence band (area between upper and lower)
            const bandData = years.map(y => {
                const pt = child.backcasted_yields.find(p => p.year === y);
                return pt ? pt.upper_bound - pt.lower_bound : null;
            });
            series.push({
                name: `${label} CI`,
                type: 'line',
                data: bandData,
                lineStyle: { opacity: 0 },
                symbol: 'none',
                stack: `ci-${idx}`,
                areaStyle: { color, opacity: BAND_OPACITY },
                silent: true,
                z: 1,
            });

            // main predicted yield line
            const mainData = years.map(y => {
                const pt = child.backcasted_yields.find(p => p.year === y);
                return pt ? pt.predicted_yield : null;
            });
            series.push({
                name: label,
                type: 'line',
                data: mainData,
                smooth: true,
                symbol: 'circle',
                symbolSize: 4,
                lineStyle: { width: 2.5, color },
                itemStyle: { color },
                z: 10,
            });
        });

        // vertical split year marker
        const markLineData = data.split_year >= years[0] && data.split_year <= years[years.length - 1]
            ? [{ xAxis: String(data.split_year), label: { formatter: `Split ${data.split_year}`, fontSize: 11, color: '#ef4444' }, lineStyle: { type: 'dashed', color: '#ef4444', width: 1.5 } }]
            : [];

        if (markLineData.length > 0 && series.length > 0) {
            (series[series.length - 1] as Record<string, unknown>).markLine = {
                silent: true,
                symbol: ['none', 'none'],
                data: markLineData,
            };
        }

        return {
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(15,23,42,0.92)',
                borderColor: '#334155',
                textStyle: { color: '#f8fafc', fontSize: 12 },
                formatter: (params: Array<{ seriesName: string; value: number | null; axisValue: string; color: string }>) => {
                    const year = params[0]?.axisValue;
                    const lines = params
                        .filter(p => !p.seriesName.includes('upper') && !p.seriesName.includes('CI') && p.value !== null)
                        .map(p => `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:4px"></span>${p.seriesName}: <b>${Math.round(p.value as number)}</b> kg/ha`);
                    return `<div style="font-weight:600;margin-bottom:4px">${year}</div>${lines.join('<br/>')}`;
                },
            },
            legend: {
                data: childEntries.map(([cdk], idx) => ({
                    name: cdkLabel(cdk),
                    itemStyle: { color: CHILD_COLORS[idx % CHILD_COLORS.length] },
                })),
                bottom: 0,
                textStyle: { color: '#64748b', fontSize: 11 },
            },
            grid: { left: '4%', right: '4%', bottom: '14%', top: '6%', containLabel: true },
            xAxis: {
                type: 'category',
                data: years.map(String),
                axisLabel: { color: '#64748b', fontSize: 10, interval: Math.max(0, Math.floor(years.length / 12)) },
                axisLine: { lineStyle: { color: '#e2e8f0' } },
            },
            yAxis: {
                type: 'value',
                name: 'Yield (kg/ha)',
                nameTextStyle: { color: '#94a3b8', fontSize: 11 },
                splitLine: { lineStyle: { color: '#f1f5f9' } },
                axisLabel: { color: '#64748b', fontSize: 10 },
            },
            series,
        };
    }, [data, hasData]);

    /* ── render ───────────────────────────────────────────────────────────── */
    return (
        <main className="page-container">
            {/* ── Header ────────────────────────────────────────────────── */}
            <div className="flex flex-col md:flex-row md:items-center gap-4 mb-8 border-b border-slate-200 pb-6">
                <div className="p-3 bg-amber-100 text-amber-700 rounded-xl shadow-inner mt-1 shrink-0">
                    <History size={24} />
                </div>
                <div>
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-[10px] font-bold text-amber-700 uppercase tracking-widest mb-2">
                        <GitBranch size={10} /> ML Yield Backcasting
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Yield Backcast Engine</h1>
                    <p className="text-sm text-slate-500 mt-1 max-w-3xl">
                        Reconstruct <strong>pre-split yield histories</strong> for newly-formed child districts using ML models
                        trained on the parent&apos;s historical data, area ratios, and sibling trends. Includes confidence
                        intervals and mass-balance conservation checks.
                    </p>
                </div>
            </div>

            {/* ── Controls ──────────────────────────────────────────────── */}
            <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6 shadow-sm grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 items-end">
                {/* State */}
                <div>
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">State</label>
                    <select
                        value={selectedState}
                        onChange={e => { setSelectedState(e.target.value); setSelectedEventIdx(-1); }}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-amber-500 outline-none"
                    >
                        <option value="">Select state…</option>
                        {states.map(s => <option key={s as string} value={s as string}>{s as string}</option>)}
                    </select>
                </div>

                {/* Split Event */}
                <div className="lg:col-span-2">
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Split Event</label>
                    <select
                        value={selectedEventIdx}
                        onChange={e => setSelectedEventIdx(Number(e.target.value))}
                        disabled={!splitEvents || splitEvents.length === 0}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-amber-500 outline-none disabled:opacity-50"
                    >
                        <option value={-1}>
                            {!selectedState ? 'Pick a state first' : !splitEvents ? 'Loading…' : splitEvents.length === 0 ? 'No splits found' : 'Select split event…'}
                        </option>
                        {splitEvents?.map((ev, idx) => (
                            <option key={ev.id} value={idx}>
                                {ev.parent_name} → {ev.children_names.join(' + ')} ({ev.split_year})
                            </option>
                        ))}
                    </select>
                </div>

                {/* Crop */}
                <div>
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Crop</label>
                    <select
                        value={selectedCrop}
                        onChange={e => setSelectedCrop(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-amber-500 outline-none"
                    >
                        {['rice', 'wheat', 'cotton', 'sugarcane', 'maize', 'groundnut', 'sorghum', 'chickpea'].map(c => (
                            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                        ))}
                    </select>
                </div>

                {/* Start Year */}
                <div>
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Start Year</label>
                    <select
                        value={startYear}
                        onChange={e => setStartYear(Number(e.target.value))}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-amber-500 outline-none"
                    >
                        {[1966, 1970, 1975, 1980, 1985, 1990, 1995, 2000].map(y => (
                            <option key={y} value={y}>{y}</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* ── Loading ───────────────────────────────────────────────── */}
            {isLoading && (
                <div className="flex items-center justify-center py-20 bg-white border border-slate-200 rounded-xl">
                    <div className="w-8 h-8 border-2 border-amber-200 border-t-amber-600 rounded-full animate-spin mr-3" />
                    <span className="text-sm text-slate-500 font-medium">Running yield backcasting models…</span>
                </div>
            )}

            {/* ── Error ─────────────────────────────────────────────────── */}
            {isError && !isNoDataError && (
                <div className="bg-white border border-rose-200 rounded-xl p-10 text-center shadow-sm">
                    <AlertTriangle size={36} className="mx-auto mb-3 text-rose-400" />
                    <h3 className="text-lg font-bold text-slate-700">Backcasting Failed</h3>
                    <p className="text-sm text-slate-500 mt-1">{(error as Error)?.message || 'Model could not converge with available data.'}</p>
                </div>
            )}

            {/* ── No data ───────────────────────────────────────────────── */}
            {!isLoading && canQuery && !hasData && (!isError || isNoDataError) && (
                <div className="bg-white border border-slate-200 rounded-xl p-10 text-center shadow-sm">
                    <Info size={36} className="mx-auto mb-3 text-slate-300" />
                    <h3 className="text-lg font-bold text-slate-700">No Backcast Data</h3>
                    <p className="text-sm text-slate-500 mt-1">{apiError?.message || 'Insufficient historical data for the selected split event and crop.'}</p>
                </div>
            )}

            {/* ── Empty state (nothing selected) ─────────────────────────── */}
            {!isLoading && !canQuery && !isError && (
                <div className="bg-white border border-dashed border-slate-300 rounded-xl p-10 text-center shadow-sm">
                    <History size={48} className="mx-auto mb-4 text-amber-300" />
                    <h3 className="text-lg font-bold text-slate-700">Select a Split Event to Begin</h3>
                    <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
                        Choose a state and split event from the controls above. The engine will estimate pre-split yield histories
                        for each child district using ML models trained on the parent&apos;s data.
                    </p>
                </div>
            )}

            {/* ── Results ────────────────────────────────────────────────── */}
            {hasData && data && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {/* KPI Cards */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        <MethodCard data={data} />
                        <ChildrenCountCard data={data} />
                        <ConservationCard data={data} />
                        <YearsCard data={data} />
                    </div>

                    {/* Chart */}
                    {chartOption && (
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <h2 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
                                <TrendingUp size={16} className="text-amber-600" /> Backcasted Yield Time Series
                            </h2>
                            <div className="h-[420px]">
                                <ReactECharts option={chartOption} style={{ height: '100%', width: '100%' }} />
                            </div>
                            <div className="text-xs text-center text-slate-400 mt-2">
                                Shaded bands show prediction confidence intervals • Dashed red line marks the split year
                            </div>
                        </div>
                    )}

                    {/* Conservation check banner */}
                    <ConservationBanner data={data} />

                    {/* Per-child detail cards (expandable) */}
                    <div className="space-y-3">
                        <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                            <Cpu size={16} className="text-amber-600" /> Model Details by Child District
                        </h2>
                        {Object.entries(data.children).map(([cdk, child], idx) => (
                            <ChildDetailCard
                                key={cdk}
                                cdk={cdk}
                                child={child}
                                color={CHILD_COLORS[idx % CHILD_COLORS.length]}
                                expanded={expandedChild === cdk}
                                onToggle={() => setExpandedChild(expandedChild === cdk ? null : cdk)}
                            />
                        ))}
                    </div>

                    {/* Data Table */}
                    <DataTable data={data} />

                    {/* AI Narrative */}
                    <AINarrative narrative={data.ai_narrative} />
                </div>
            )}
        </main>
    );
}

/* ════════════════════════════════════════════════════════════════════════ */
/*  SUB-COMPONENTS                                                        */
/* ════════════════════════════════════════════════════════════════════════ */

function MethodCard({ data }: { data: BackcastResponse }) {
    const badge = methodBadge(data.method);
    return (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Primary Method</div>
            <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-bold border ${badge.cls}`}>
                <Cpu size={14} /> {badge.label}
            </div>
            <div className="text-xs text-slate-500 mt-2">Highest-available model tier</div>
        </div>
    );
}

function ChildrenCountCard({ data }: { data: BackcastResponse }) {
    const count = Object.keys(data.children).length;
    return (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Child Districts</div>
            <div className="text-2xl font-bold font-mono text-slate-700">{count}</div>
            <div className="text-xs text-slate-500 mt-1">Backcasted from parent {cdkLabel(data.parent_cdk)}</div>
        </div>
    );
}

function ConservationCard({ data }: { data: BackcastResponse }) {
    const cc = data.conservation_check;
    return (
        <div className={`border rounded-xl p-5 shadow-sm ${cc.is_valid ? 'bg-emerald-50 border-emerald-200' : 'bg-rose-50 border-rose-200'}`}>
            <div className={`text-[10px] uppercase font-bold mb-1 ${cc.is_valid ? 'text-emerald-700/70' : 'text-rose-700/70'}`}>
                Conservation Check
            </div>
            <div className="flex items-center gap-2">
                {cc.is_valid
                    ? <ShieldCheck size={20} className="text-emerald-600" />
                    : <ShieldAlert size={20} className="text-rose-600" />}
                <span className={`text-lg font-bold ${cc.is_valid ? 'text-emerald-800' : 'text-rose-800'}`}>
                    {cc.is_valid ? 'Passed' : 'Failed'}
                </span>
            </div>
            <div className="text-xs text-slate-600 mt-1">
                Relative error: <span className="font-mono font-bold">{(cc.relative_error * 100).toFixed(1)}%</span>
            </div>
        </div>
    );
}

function YearsCard({ data }: { data: BackcastResponse }) {
    const allYears: number[] = [];
    Object.values(data.children).forEach(c => c.backcasted_yields.forEach(p => allYears.push(p.year)));
    const minY = allYears.length > 0 ? Math.min(...allYears) : 0;
    const maxY = allYears.length > 0 ? Math.max(...allYears) : 0;
    return (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Backcast Range</div>
            <div className="text-2xl font-bold font-mono text-amber-600">{minY}–{maxY}</div>
            <div className="text-xs text-slate-500 mt-1">{allYears.length > 0 ? maxY - minY + 1 : 0} years estimated</div>
        </div>
    );
}

function ConservationBanner({ data }: { data: BackcastResponse }) {
    const cc = data.conservation_check;
    if (cc.is_valid) return null;
    return (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-sm text-rose-800 shadow-sm flex items-start gap-3">
            <AlertTriangle size={18} className="shrink-0 mt-0.5" />
            <div>
                <strong>Conservation Warning:</strong> The sum of backcasted children yields diverges from the parent yield
                by <span className="font-mono font-bold">{(cc.relative_error * 100).toFixed(1)}%</span>. This may
                indicate insufficient overlapping training data. Interpret results with caution.
            </div>
        </div>
    );
}

function ChildDetailCard({
    cdk,
    child,
    color,
    expanded,
    onToggle,
}: {
    cdk: string;
    child: BackcastChildResult;
    color: string;
    expanded: boolean;
    onToggle: () => void;
}) {
    const stats = child.model_stats;
    const badge = child.backcasted_yields.length > 0 ? methodBadge(child.backcasted_yields[0].method) : methodBadge('unknown');
    const avgConfidence = child.backcasted_yields.length > 0
        ? child.backcasted_yields.reduce((s, p) => s + p.confidence, 0) / child.backcasted_yields.length
        : 0;

    return (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            <button
                onClick={onToggle}
                className="w-full flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition-colors text-left"
            >
                <div className="flex items-center gap-3">
                    <span className="w-3 h-3 rounded-full shrink-0" style={{ background: color }} />
                    <span className="font-bold text-sm text-slate-800">{cdkLabel(cdk)}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${badge.cls}`}>
                        {badge.label}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">{child.backcasted_yields.length} pts</span>
                </div>
                <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-500">Avg confidence: <span className="font-mono font-bold">{(avgConfidence * 100).toFixed(0)}%</span></span>
                    {expanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                </div>
            </button>
            {expanded && (
                <div className="px-5 pb-4 pt-2 border-t border-slate-100 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                        <h4 className="text-[10px] uppercase font-bold text-slate-400 mb-2">Model Statistics</h4>
                        <div className="space-y-1">
                            {Object.entries(stats).map(([key, val]) => (
                                <div key={key} className="flex justify-between">
                                    <span className="text-slate-500">{key.replace(/_/g, ' ')}</span>
                                    <span className="font-mono font-bold text-slate-700">
                                        {typeof val === 'number' ? val.toFixed(4) : String(val)}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div>
                        <h4 className="text-[10px] uppercase font-bold text-slate-400 mb-2">Features Used</h4>
                        <div className="flex flex-wrap gap-1.5">
                            {child.features_used.map(f => (
                                <span key={f} className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full border border-slate-200 font-mono">
                                    {f}
                                </span>
                            ))}
                        </div>
                        {Object.keys(child.feature_importances).length > 0 && (
                            <>
                                <h4 className="text-[10px] uppercase font-bold text-slate-400 mb-2 mt-4">Feature Importances</h4>
                                <div className="space-y-1.5">
                                    {Object.entries(child.feature_importances).sort(([, a], [, b]) => b - a).map(([feat, imp]) => (
                                        <div key={feat} className="flex items-center gap-2">
                                            <span className="text-xs text-slate-500 w-24 truncate">{feat}</span>
                                            <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                                                <div className="h-full rounded-full" style={{ width: `${imp * 100}%`, background: color }} />
                                            </div>
                                            <span className="text-xs font-mono text-slate-600 w-12 text-right">{(imp * 100).toFixed(1)}%</span>
                                        </div>
                                    ))}
                                </div>
                            </>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

function DataTable({ data }: { data: BackcastResponse }) {
    const childEntries = Object.entries(data.children);
    // Flatten all year points across children for the table
    const allYears = new Set<number>();
    childEntries.forEach(([, child]) => child.backcasted_yields.forEach(p => allYears.add(p.year)));
    const years = [...allYears].sort((a, b) => a - b);

    return (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            <div className="p-4 border-b border-slate-200 bg-slate-50">
                <h2 className="text-sm font-bold text-slate-900">Backcast Data Table</h2>
                <p className="text-xs text-slate-500 mt-0.5">Predicted yields (kg/ha) for each child district by year</p>
            </div>
            <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
                <table className="w-full text-left text-sm">
                    <thead className="bg-white sticky top-0 border-b border-slate-200 z-10">
                        <tr className="text-xs uppercase text-slate-400">
                            <th className="py-2 px-4">Year</th>
                            {childEntries.map(([cdk], idx) => (
                                <th key={cdk} className="py-2 px-4 text-right">
                                    <span className="inline-flex items-center gap-1">
                                        <span className="w-2 h-2 rounded-full" style={{ background: CHILD_COLORS[idx % CHILD_COLORS.length] }} />
                                        {cdkLabel(cdk)}
                                    </span>
                                </th>
                            ))}
                            {childEntries.map(([cdk]) => (
                                <th key={`${cdk}-conf`} className="py-2 px-4 text-right text-slate-300">
                                    Conf.
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                        {years.map(year => {
                            const isSplitYear = year === data.split_year;
                            return (
                                <tr key={year} className={`hover:bg-slate-50 transition-colors ${isSplitYear ? 'bg-red-50/50' : ''}`}>
                                    <td className={`py-1.5 px-4 font-mono ${isSplitYear ? 'font-bold text-red-600' : 'text-slate-600'}`}>
                                        {year}{isSplitYear ? ' ←' : ''}
                                    </td>
                                    {childEntries.map(([cdk, child]) => {
                                        const pt = child.backcasted_yields.find(p => p.year === year);
                                        return (
                                            <td key={cdk} className="py-1.5 px-4 text-right font-mono text-slate-700">
                                                {pt ? Math.round(pt.predicted_yield).toLocaleString() : '—'}
                                            </td>
                                        );
                                    })}
                                    {childEntries.map(([cdk, child]) => {
                                        const pt = child.backcasted_yields.find(p => p.year === year);
                                        return (
                                            <td key={`${cdk}-conf`} className="py-1.5 px-4 text-right font-mono text-xs">
                                                {pt ? (
                                                    <span className={pt.confidence >= 0.7 ? 'text-emerald-600' : pt.confidence >= 0.4 ? 'text-amber-600' : 'text-rose-500'}>
                                                        {(pt.confidence * 100).toFixed(0)}%
                                                    </span>
                                                ) : '—'}
                                            </td>
                                        );
                                    })}
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
