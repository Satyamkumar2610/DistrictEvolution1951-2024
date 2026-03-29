'use client';

import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, type AnalysisResult, type SplitDistrict, type SplitImpactQueryParams, type SplitImpactResult, type SplitSpecializationResult } from '../../services/api';
import {
    GitBranch, Download, FileText, TrendingUp, TrendingDown,
    Minus, ChevronDown, ChevronUp, AlertCircle, ArrowRight,
    Activity, Target, Layers, PieChart
} from 'lucide-react';
import ReactECharts from 'echarts-for-react';

const CROPS = ['wheat', 'rice', 'maize', 'sorghum', 'groundnut', 'cotton', 'sugarcane'];
const METRICS = [
    { value: 'yield', label: 'Yield (Kg/Ha)' },
    { value: 'area', label: 'Area (Ha)' },
    { value: 'production', label: 'Production (Tonnes)' },
];
type ExpandedSection = 'pre' | 'post' | 'impact' | 'spec';

const isNonNullString = (value: string | null): value is string => Boolean(value);

function getStdDev(variance: number | undefined) {
    if (variance == null) {
        return '—';
    }

    return Math.sqrt(Math.max(variance, 0)).toFixed(1);
}

function StatBox({ label, value, unit, color = 'text-slate-900', sub }: {
    label: string; value: string | number; unit?: string; color?: string; sub?: string;
}) {
    return (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-center">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-1">{label}</div>
            <div className={`text-xl font-bold font-mono ${color}`}>{value}<span className="text-xs text-slate-400 ml-1">{unit}</span></div>
            {sub && <div className="text-[10px] text-slate-500 mt-0.5">{sub}</div>}
        </div>
    );
}

function AssessmentBadge({ assessment }: { assessment: string }) {
    const map: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
        positive: { bg: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700', icon: <TrendingUp size={12} /> },
        negative: { bg: 'bg-red-50 border-red-200', text: 'text-red-700', icon: <TrendingDown size={12} /> },
        neutral: { bg: 'bg-amber-50 border-amber-200', text: 'text-amber-700', icon: <Minus size={12} /> },
    };
    const s = map[assessment] || map.neutral;
    return (
        <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold ${s.bg} ${s.text} border`}>
            {s.icon} {assessment.charAt(0).toUpperCase() + assessment.slice(1)} Impact
        </span>
    );
}

export default function SplitReportPage() {
    const [selectedState, setSelectedState] = useState('');
    const [selectedEvent, setSelectedEvent] = useState<SplitDistrict | null>(null);
    const [crop, setCrop] = useState('wheat');
    const [metric, setMetric] = useState('yield');
    const [generated, setGenerated] = useState(false);
    const [expandedSections, setExpandedSections] = useState<Record<ExpandedSection, boolean>>({
        pre: true,
        post: true,
        impact: true,
        spec: true,
    });

    // Queries
    const { data: summaryData } = useQuery({ queryKey: ['stateSummary'], queryFn: api.getSummary, staleTime: 3600000 });
    const states = useMemo(() => {
        if (!summaryData?.states) return [];
        if (Array.isArray(summaryData.states)) return summaryData.states;
        return Object.keys(summaryData.states).sort();
    }, [summaryData]);

    const { data: unmappedSplits, isLoading: loadingUnmapped } = useQuery({
        queryKey: ['unmappedSplits'],
        queryFn: api.getUnmappedSplits,
        staleTime: 3600000,
    });

    const { data: splitEvents, isLoading: loadingEvents } = useQuery({
        queryKey: ['splitEvents', selectedState],
        queryFn: () => api.getSplitEvents(selectedState),
        enabled: !!selectedState,
    });

    // Full analysis from the backend
    const selectedParentCdk = selectedEvent?.parent_cdk ?? null;
    const resolvedChildCdks = useMemo(
        () => selectedEvent?.children_cdks.filter(isNonNullString) ?? [],
        [selectedEvent],
    );

    const analysisParams: SplitImpactQueryParams | null = selectedEvent && selectedParentCdk && generated ? {
        parent: selectedParentCdk,
        children: resolvedChildCdks.join(','),
        splitYear: selectedEvent.split_year,
        crop,
        metric,
        mode: 'before_after',
    } : null;

    const { data: analysis, isLoading: loadingAnalysis } = useQuery<AnalysisResult>({
        queryKey: ['split-report-analysis', analysisParams],
        queryFn: () => api.getAnalysis(analysisParams!),
        enabled: !!analysisParams,
        retry: 1,
    });

    // Quick split-impact for summary stats
    const { data: impactData } = useQuery<SplitImpactResult>({
        queryKey: ['split-impact-quick', selectedEvent?.parent_cdk, selectedEvent?.children_cdks, selectedEvent?.split_year, crop],
        queryFn: () => api.getSplitImpact(
            selectedParentCdk!,
            resolvedChildCdks,
            selectedEvent!.split_year,
            crop,
        ),
        enabled: !!selectedEvent && generated && !!selectedParentCdk,
    });

    const { data: specData } = useQuery<SplitSpecializationResult>({
        queryKey: ['split-spec', selectedEvent?.parent_cdk, selectedEvent?.children_cdks, selectedEvent?.split_year],
        queryFn: () => api.getSplitSpecialization(
            selectedParentCdk!,
            resolvedChildCdks,
            selectedEvent!.split_year
        ),
        enabled: !!selectedEvent && generated && !!selectedParentCdk,
    });

    const advStats = analysis?.advanced_stats ?? analysis?.advancedStats;
    const hasData = analysis && Array.isArray(analysis.data) && analysis.data.length > 0;

    // Chart data
    const chartOption = useMemo(() => {
        if (!analysis?.data || !analysis?.series) return null;
        const timelineData = analysis.data;
        const seriesMeta = analysis.series;
        const years = timelineData.map((d) => d.year);
        const series = seriesMeta.map((s) => ({
            name: s.label,
            type: 'line',
            data: timelineData.map((d) => d[s.id] ?? null),
            smooth: true,
            symbol: 'circle',
            symbolSize: 5,
            connectNulls: false,
            lineStyle: {
                width: 2.5,
                type: s.style === 'dashed' ? 'dashed' : 'solid',
            },
        }));

        return {
            tooltip: {
                trigger: 'axis',
                backgroundColor: '#fff',
                borderColor: '#e2e8f0',
                textStyle: { color: '#1e293b', fontSize: 12 },
            },
            legend: {
                bottom: 0,
                textStyle: { color: '#64748b', fontSize: 11 },
                icon: 'roundRect',
            },
            grid: { top: 20, right: 20, bottom: 40, left: 10, containLabel: true },
            xAxis: {
                type: 'category',
                data: years,
                axisLine: { lineStyle: { color: '#e2e8f0' } },
                axisLabel: { color: '#64748b', fontSize: 11 },
            },
            yAxis: {
                type: 'value',
                splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } },
                axisLabel: { color: '#64748b', fontSize: 11 },
            },
            series,
            color: ['#6366f1', '#10b981', '#f59e0b', '#ec4899', '#06b6d4'],
            // Mark split year
            ...(selectedEvent ? {
                visualMap: undefined,
                markLine: undefined,
            } : {}),
        };
    }, [analysis, selectedEvent]);

    const radarOption = useMemo(() => {
        if (!specData) return null;

        const indicator = specData.crops.map((c: string) => ({ name: c.charAt(0).toUpperCase() + c.slice(1).replace('_', ' '), max: 100 }));

        const seriesData = [
            {
                value: specData.crops.map((c: string) => specData.parent.pre_mix[c]),
                name: `${specData.parent.name} (Pre-Split)`,
                itemStyle: { color: '#6366f1' },
                lineStyle: { type: 'dashed' },
                areaStyle: { opacity: 0.1 }
            }
        ];

        const colors = ['#10b981', '#f59e0b', '#ec4899', '#06b6d4'];
        let idx = 0;
        for (const [childName, childData] of Object.entries(specData.children)) {
            const cData = childData as { mix: Record<string, number> };
            seriesData.push({
                value: specData.crops.map((c: string) => cData.mix[c]),
                name: `${childName} (Post-Split)`,
                itemStyle: { color: colors[idx % colors.length] },
                lineStyle: { type: 'solid' },
                areaStyle: { opacity: 0.2 }
            });
            idx++;
        }

        return {
            tooltip: { trigger: 'item' },
            legend: { bottom: 0, textStyle: { fontSize: 11, color: '#64748b' } },
            radar: {
                indicator,
                shape: 'circle',
                splitNumber: 5,
                axisName: { color: '#475569', fontSize: 10, fontWeight: 'bold' },
                splitLine: { lineStyle: { color: ['#e2e8f0'].reverse() } },
                splitArea: { show: false },
                axisLine: { lineStyle: { color: '#e2e8f0' } }
            },
            series: [{
                name: 'Crop Mix',
                type: 'radar',
                data: seriesData,
                symbolSize: 4
            }]
        };
    }, [specData]);

    // Export handlers
    const handleExportJSON = () => {
        if (!analysis) return;
        const exportData = {
            report_type: 'pre_post_split_comparative_analysis',
            generated_at: new Date().toISOString(),
            config: { state: selectedState, event: selectedEvent, crop, metric },
            analysis,
            impact_summary: impactData,
        };
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `split_report_${selectedEvent?.parent_district}_${crop}_${metric}.json`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const handleExportCSV = () => {
        if (!analysis?.data) return;
        const rows = analysis.data;
        if (!rows.length) return;
        const headers = Object.keys(rows[0]).join(',');
        const csv = [headers, ...rows.map((r: Record<string, unknown>) => Object.values(r).join(','))].join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `split_report_${selectedEvent?.parent_district}_${crop}_${metric}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const toggleSection = (key: ExpandedSection) => {
        setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
    };

    return (
        <main className="w-full h-full text-slate-900">
            <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
                {/* Header */}
                <div className="mb-8">
                    <div className="flex items-center gap-3 mb-1">
                        <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center">
                            <GitBranch className="text-indigo-600" size={20} />
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Split Comparative Report</h1>
                            <p className="text-sm text-slate-500">Pre-split vs Post-split agricultural performance analysis</p>
                        </div>
                    </div>
                </div>

                {/* Configuration Panel */}
                <div className="bg-white border border-slate-200 rounded-xl p-5 mb-8 shadow-sm">
                    <h2 className="text-xs font-bold uppercase text-slate-500 tracking-wider mb-4">Report Configuration</h2>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                        {/* State */}
                        <div>
                            <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">State</label>
                            <select
                                value={selectedState}
                                onChange={(e) => {
                                    setSelectedState(e.target.value);
                                    setSelectedEvent(null);
                                }}
                                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
                            >
                                <option value="">Select state...</option>
                                {states.map((stateName) => <option key={stateName} value={stateName}>{stateName}</option>)}
                            </select>
                        </div>

                        {/* Split Event */}
                        <div>
                            <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Split Event</label>
                            <select
                                value={selectedEvent?.id || ''}
                                onChange={(e) => {
                                    const ev = splitEvents?.find((splitEvent) => splitEvent.id === e.target.value);
                                    setSelectedEvent(ev || null);
                                    setGenerated(false);
                                }}
                                disabled={!selectedState || loadingEvents}
                                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none disabled:opacity-50"
                            >
                                <option value="">Select split event...</option>
                                {splitEvents?.map((ev) => (
                                    <option key={ev.id} value={ev.id}>
                                        {ev.parent_district} → {ev.children_districts.length} districts ({ev.split_year})
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Crop */}
                        <div>
                            <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Crop</label>
                            <select
                                value={crop}
                                onChange={(e) => { setCrop(e.target.value); setGenerated(false); }}
                                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none capitalize"
                            >
                                {CROPS.map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                        </div>

                        {/* Metric */}
                        <div>
                            <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Metric</label>
                            <select
                                value={metric}
                                onChange={(e) => { setMetric(e.target.value); setGenerated(false); }}
                                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
                            >
                                {METRICS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                            </select>
                        </div>
                    </div>

                    {/* Selected event preview + generate button */}
                    <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                        {selectedEvent ? (
                            <div className="text-sm text-slate-600">
                                <span className="font-bold text-slate-900">{selectedEvent.parent_district}</span>
                                <ArrowRight size={12} className="inline mx-1.5 text-slate-400" />
                                <span className="text-indigo-600 font-semibold">{selectedEvent.children_districts?.join(', ')}</span>
                                <span className="text-slate-400 ml-2">({selectedEvent.split_year})</span>
                            </div>
                        ) : (
                            <div className="text-sm text-slate-400 italic">Select a state and split event to begin</div>
                        )}
                        <button
                            onClick={() => setGenerated(true)}
                            disabled={!selectedEvent}
                            className="px-5 py-2 bg-indigo-600 text-white text-sm font-bold rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-sm"
                        >
                            Generate Report
                        </button>
                    </div>
                </div>

                {/* Loading */}
                {generated && loadingAnalysis && (
                    <div className="flex items-center justify-center py-20">
                        <div className="w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mr-3" />
                        <span className="text-sm text-slate-500 font-medium">Analyzing split impact data...</span>
                    </div>
                )}

                {/* No data */}
                {generated && !loadingAnalysis && !hasData && (
                    <div className="bg-white border border-slate-200 rounded-xl p-10 text-center shadow-sm">
                        <AlertCircle size={36} className="mx-auto mb-3 text-slate-300" />
                        <h3 className="text-lg font-bold text-slate-700">No Data Available</h3>
                        <p className="text-sm text-slate-500 mt-1">
                            No {crop} {metric} data found for <span className="font-semibold">{selectedEvent?.parent_district}</span>.
                            Try a different crop or metric.
                        </p>
                    </div>
                )}

                {/* ══════════════════ REPORT OUTPUT ══════════════════ */}
                {generated && hasData && selectedEvent && (
                    <div className="space-y-6 animate-in">
                        {/* Export bar */}
                        <div className="flex items-center justify-between">
                            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                                <FileText size={18} className="text-indigo-600" />
                                Report: {selectedEvent.parent_district} Split ({selectedEvent.split_year})
                            </h2>
                            <div className="flex gap-2">
                                <button onClick={handleExportJSON} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold border border-slate-300 rounded-lg hover:bg-slate-50 transition text-slate-600">
                                    <Download size={12} /> JSON
                                </button>
                                <button onClick={handleExportCSV} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold border border-slate-300 rounded-lg hover:bg-slate-50 transition text-slate-600">
                                    <Download size={12} /> CSV
                                </button>
                            </div>
                        </div>

                        {/* ─── SECTION 1: PRE-SPLIT ─── */}
                        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                            <button
                                onClick={() => toggleSection('pre')}
                                className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-50 transition"
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
                                        <Layers size={16} className="text-blue-600" />
                                    </div>
                                    <div className="text-left">
                                        <h3 className="text-sm font-bold text-slate-900">Section 1: Pre-Split Analysis</h3>
                                        <p className="text-xs text-slate-500">Parent district performance before boundary change</p>
                                    </div>
                                </div>
                                {expandedSections.pre ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                            </button>

                            {expandedSections.pre && (
                                <div className="px-5 pb-5 border-t border-slate-100 pt-4">
                                    <div className="mb-3">
                                        <span className="text-xs text-slate-500 font-medium">District: </span>
                                        <span className="text-sm font-bold text-slate-900">{selectedEvent.parent_district}</span>
                                        <span className="text-xs text-slate-400 ml-2">
                                            (Period: before {selectedEvent.split_year})
                                        </span>
                                    </div>

                                    {advStats?.pre ? (
                                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                            <StatBox label="Mean Yield" value={advStats.pre.mean?.toFixed(1) ?? '—'} unit="kg/ha" color="text-blue-700" />
                                            <StatBox label="Std Dev" value={getStdDev(advStats.pre.variance)} unit="kg/ha" />
                                            <StatBox label="CV %" value={advStats.pre.cv?.toFixed(1) ?? '—'} unit="%" sub={advStats.pre.cv > 25 ? 'High variability' : 'Stable'} />
                                            <StatBox label="Data Points" value={advStats.pre.n_observations ?? '—'} unit="yrs" />
                                        </div>
                                    ) : impactData?.before ? (
                                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                                            <StatBox label="Average Yield" value={impactData.before.average?.toFixed(1) ?? '—'} unit="kg/ha" color="text-blue-700" />
                                            <StatBox label="Data Years" value={impactData.before.years?.length ?? 0} unit="yrs" />
                                            <StatBox label="Year Range" value={impactData.before.years?.length ? `${impactData.before.years[0]}–${impactData.before.years[impactData.before.years.length - 1]}` : '—'} />
                                        </div>
                                    ) : (
                                        <p className="text-sm text-slate-400 italic">Pre-split statistics not available.</p>
                                    )}

                                    {/* Pre-split yearly data table */}
                                    {impactData?.before?.years && impactData.before.yields && (
                                        <div className="mt-4">
                                            <h4 className="text-xs font-bold text-slate-500 uppercase mb-2">Yearly Data</h4>
                                            <div className="overflow-x-auto">
                                                <table className="text-xs w-full">
                                                    <thead>
                                                        <tr className="bg-slate-50">
                                                            <th className="px-3 py-2 text-left text-slate-500 font-semibold">Year</th>
                                                            <th className="px-3 py-2 text-right text-slate-500 font-semibold capitalize">{metric} (kg/ha)</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {impactData.before.years.map((yr: number, i: number) => (
                                                            <tr key={yr} className="border-t border-slate-100">
                                                                <td className="px-3 py-1.5 text-slate-700 font-mono">{yr}</td>
                                                                <td className="px-3 py-1.5 text-right font-mono font-semibold text-slate-900">
                                                                    {impactData.before.yields[i]?.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                                                                </td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* ─── SECTION 2: POST-SPLIT ─── */}
                        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                            <button
                                onClick={() => toggleSection('post')}
                                className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-50 transition"
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center">
                                        <Activity size={16} className="text-emerald-600" />
                                    </div>
                                    <div className="text-left">
                                        <h3 className="text-sm font-bold text-slate-900">Section 2: Post-Split Analysis</h3>
                                        <p className="text-xs text-slate-500">Child district performance after boundary change</p>
                                    </div>
                                </div>
                                {expandedSections.post ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                            </button>

                            {expandedSections.post && (
                                <div className="px-5 pb-5 border-t border-slate-100 pt-4">
                                    <div className="mb-3 text-xs text-slate-500 font-medium">
                                        Split into <span className="font-bold text-slate-900">{selectedEvent.children_districts?.length}</span> districts in <span className="font-bold text-slate-900">{selectedEvent.split_year}</span>
                                    </div>

                                    {advStats?.post ? (
                                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                                            <StatBox label="Combined Mean" value={advStats.post.mean?.toFixed(1) ?? '—'} unit="kg/ha" color="text-emerald-700" />
                                            <StatBox label="Std Dev" value={getStdDev(advStats.post.variance)} unit="kg/ha" />
                                            <StatBox label="CV %" value={advStats.post.cv?.toFixed(1) ?? '—'} unit="%" sub={advStats.post.cv > 25 ? 'High variability' : 'Stable'} />
                                            <StatBox label="Data Points" value={advStats.post.n_observations ?? '—'} unit="yrs" />
                                        </div>
                                    ) : impactData?.after ? (
                                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
                                            <StatBox label="Combined Avg" value={impactData.after.combined_average?.toFixed(1) ?? '—'} unit="kg/ha" color="text-emerald-700" />
                                            <StatBox label="Children" value={Object.keys(impactData.after.by_child || {}).length} unit="districts" />
                                        </div>
                                    ) : null}

                                    {/* Per-child breakdown */}
                                    {impactData?.after?.by_child && (
                                        <div>
                                            <h4 className="text-xs font-bold text-slate-500 uppercase mb-2">Child District Breakdown</h4>
                                            <div className="grid gap-2">
                                                {Object.entries(impactData.after.by_child).map(([cdk, child]) => {
                                                    const childIndex = selectedEvent.children_cdks.indexOf(cdk);
                                                    const childName = childIndex >= 0 ? selectedEvent.children_districts?.[childIndex] || cdk : cdk;
                                                    return (
                                                        <div key={cdk} className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-lg px-4 py-2.5">
                                                            <div>
                                                                <span className="text-sm font-semibold text-slate-900">{childName}</span>
                                                                <span className="text-[10px] text-slate-400 ml-2">CDK: {cdk}</span>
                                                            </div>
                                                            <div className="text-right">
                                                                <span className="text-sm font-bold font-mono text-emerald-700">{child.avg?.toFixed(1)}</span>
                                                                <span className="text-[10px] text-slate-400 ml-1">kg/ha avg</span>
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    )}

                                    {/* Advanced insights: divergence & convergence */}
                                    {advStats?.insights && (
                                        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                                            {advStats.insights.divergence && (
                                                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                                                    <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Child Divergence</div>
                                                    <div className="text-sm font-bold text-slate-900">{advStats.insights.divergence.interpretation}</div>
                                                    <div className="text-xs text-slate-500 mt-0.5">
                                                        CV across children: {advStats.insights.divergence.score?.toFixed(1)}%
                                                    </div>
                                                    {advStats.insights.divergence.best_performer && (
                                                        <div className="text-[10px] text-emerald-600 mt-1">
                                                            Best: {advStats.insights.divergence.best_performer} ({advStats.insights.divergence.best_yield?.toFixed(0)} kg/ha)
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                            {advStats.insights.convergence && (
                                                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                                                    <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Convergence Trend</div>
                                                    <div className="text-sm font-bold text-slate-900 capitalize">{advStats.insights.convergence.trend}</div>
                                                    <div className="text-xs text-slate-500 mt-0.5">{advStats.insights.convergence.interpretation}</div>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Children performance table from insights */}
                                    {advStats?.insights?.children_performance && advStats.insights.children_performance.length > 0 && (
                                        <div className="mt-4">
                                            <h4 className="text-xs font-bold text-slate-500 uppercase mb-2">Detailed Performance</h4>
                                            <div className="overflow-x-auto">
                                                <table className="text-xs w-full">
                                                    <thead>
                                                        <tr className="bg-slate-50">
                                                            <th className="px-3 py-2 text-left text-slate-500 font-semibold">#</th>
                                                            <th className="px-3 py-2 text-left text-slate-500 font-semibold">District</th>
                                                            <th className="px-3 py-2 text-right text-slate-500 font-semibold">Mean Yield</th>
                                                            <th className="px-3 py-2 text-right text-slate-500 font-semibold">CV %</th>
                                                            <th className="px-3 py-2 text-right text-slate-500 font-semibold">CAGR %</th>
                                                            <th className="px-3 py-2 text-right text-slate-500 font-semibold">Obs</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {advStats.insights.children_performance.map((cp) => (
                                                            <tr key={cp.cdk} className="border-t border-slate-100">
                                                                <td className="px-3 py-1.5 text-slate-400 font-mono">{cp.rank}</td>
                                                                <td className="px-3 py-1.5 text-slate-900 font-medium">{cp.name || cp.cdk}</td>
                                                                <td className="px-3 py-1.5 text-right font-mono font-semibold text-slate-900">{cp.mean_yield?.toFixed(1)}</td>
                                                                <td className="px-3 py-1.5 text-right font-mono text-slate-600">{cp.cv?.toFixed(1)}</td>
                                                                <td className={`px-3 py-1.5 text-right font-mono font-semibold ${cp.cagr >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                                                                    {cp.cagr >= 0 ? '+' : ''}{cp.cagr?.toFixed(2)}
                                                                </td>
                                                                <td className="px-3 py-1.5 text-right font-mono text-slate-500">{cp.observations}</td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* ─── SECTION 3: COMPARATIVE IMPACT ─── */}
                        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                            <button
                                onClick={() => toggleSection('impact')}
                                className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-50 transition"
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center">
                                        <Target size={16} className="text-indigo-600" />
                                    </div>
                                    <div className="text-left">
                                        <h3 className="text-sm font-bold text-slate-900">Section 3: Comparative Impact Assessment</h3>
                                        <p className="text-xs text-slate-500">Side-by-side pre vs post analysis with statistical tests</p>
                                    </div>
                                </div>
                                {expandedSections.impact ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                            </button>

                            {expandedSections.impact && (
                                <div className="px-5 pb-5 border-t border-slate-100 pt-4 space-y-5">
                                    {/* Impact Summary */}
                                    {impactData?.impact && (
                                        <div className="flex flex-wrap items-center gap-4 p-4 bg-slate-50 border border-slate-200 rounded-xl">
                                            <AssessmentBadge assessment={impactData.impact.assessment} />
                                            <div className="flex gap-6 flex-wrap">
                                                <div>
                                                    <div className="text-[10px] text-slate-400 uppercase font-bold">Absolute Change</div>
                                                    <div className={`text-lg font-bold font-mono ${impactData.impact.absolute_change >= 0 ? 'text-emerald-700' : 'text-red-700'}`}>
                                                        {impactData.impact.absolute_change >= 0 ? '+' : ''}{impactData.impact.absolute_change?.toFixed(1)} <span className="text-xs text-slate-400">kg/ha</span>
                                                    </div>
                                                </div>
                                                <div>
                                                    <div className="text-[10px] text-slate-400 uppercase font-bold">Percent Change</div>
                                                    <div className={`text-lg font-bold font-mono ${impactData.impact.percent_change >= 0 ? 'text-emerald-700' : 'text-red-700'}`}>
                                                        {impactData.impact.percent_change >= 0 ? '+' : ''}{impactData.impact.percent_change?.toFixed(2)}%
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Side-by-side pre vs post */}
                                    {advStats && (
                                        <div>
                                            <h4 className="text-xs font-bold text-slate-500 uppercase mb-3">Pre vs Post Comparison</h4>
                                            <div className="grid grid-cols-3 gap-px bg-slate-200 rounded-xl overflow-hidden text-sm">
                                                {/* Header */}
                                                <div className="bg-slate-100 px-4 py-2.5 font-bold text-slate-500 text-xs uppercase">Metric</div>
                                                <div className="bg-blue-50 px-4 py-2.5 font-bold text-blue-700 text-xs uppercase text-center">Pre-Split</div>
                                                <div className="bg-emerald-50 px-4 py-2.5 font-bold text-emerald-700 text-xs uppercase text-center">Post-Split</div>

                                                {/* Mean */}
                                                <div className="bg-white px-4 py-2 text-slate-700 font-medium text-xs">Mean Yield</div>
                                                <div className="bg-white px-4 py-2 text-center font-mono font-bold text-slate-900">{advStats.pre?.mean?.toFixed(1) ?? '—'}</div>
                                                <div className="bg-white px-4 py-2 text-center font-mono font-bold text-slate-900">{advStats.post?.mean?.toFixed(1) ?? '—'}</div>

                                                {/* Std Dev */}
                                                <div className="bg-white px-4 py-2 text-slate-700 font-medium text-xs">Std Dev</div>
                                                <div className="bg-white px-4 py-2 text-center font-mono text-slate-600">{getStdDev(advStats.pre?.variance)}</div>
                                                <div className="bg-white px-4 py-2 text-center font-mono text-slate-600">{getStdDev(advStats.post?.variance)}</div>

                                                {/* CV */}
                                                <div className="bg-white px-4 py-2 text-slate-700 font-medium text-xs">CV %</div>
                                                <div className="bg-white px-4 py-2 text-center font-mono text-slate-600">{advStats.pre?.cv?.toFixed(1) ?? '—'}%</div>
                                                <div className="bg-white px-4 py-2 text-center font-mono text-slate-600">{advStats.post?.cv?.toFixed(1) ?? '—'}%</div>

                                                {/* N */}
                                                <div className="bg-white px-4 py-2 text-slate-700 font-medium text-xs">Observations</div>
                                                <div className="bg-white px-4 py-2 text-center font-mono text-slate-600">{advStats.pre?.n_observations ?? '—'}</div>
                                                <div className="bg-white px-4 py-2 text-center font-mono text-slate-600">{advStats.post?.n_observations ?? '—'}</div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Advanced: Impact Stats */}
                                    {advStats?.impact && (
                                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                            <StatBox
                                                label="Mean Change"
                                                value={advStats.impact.absolute_change?.toFixed(1) ?? '—'}
                                                unit="kg/ha"
                                                color={advStats.impact.absolute_change >= 0 ? 'text-emerald-700' : 'text-red-700'}
                                            />
                                            <StatBox
                                                label="% Change"
                                                value={advStats.impact.pct_change?.toFixed(2) ?? '—'}
                                                unit="%"
                                                color={advStats.impact.pct_change >= 0 ? 'text-emerald-700' : 'text-red-700'}
                                            />
                                            <StatBox
                                                label="Impact CI"
                                                value={advStats.impact.uncertainty ? `${advStats.impact.uncertainty.lower.toFixed(1)} to ${advStats.impact.uncertainty.upper.toFixed(1)}` : '—'}
                                                color={advStats.impact.uncertainty ? 'text-indigo-700' : 'text-slate-500'}
                                                sub={advStats.impact.uncertainty ? `${Math.round((advStats.impact.uncertainty.confidence ?? 0.95) * 100)}% ${advStats.impact.uncertainty.method ?? 'confidence interval'}` : 'Not available'}
                                            />
                                        </div>
                                    )}

                                    {/* Effect size & Counterfactual */}
                                    {advStats?.insights && (
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                            {advStats.insights.effect_size && (
                                                <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
                                                    <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Cohen&apos;s d (Effect Size)</div>
                                                    <div className="text-xl font-bold font-mono text-slate-900">{advStats.insights.effect_size.cohens_d?.toFixed(3)}</div>
                                                    <div className="text-xs text-slate-500 mt-0.5 capitalize">{advStats.insights.effect_size.interpretation} effect</div>
                                                    <div className="text-[10px] text-slate-400 mt-1">Confidence: {(advStats.insights.effect_size.confidence * 100)?.toFixed(0)}%</div>
                                                </div>
                                            )}
                                            {advStats.insights.counterfactual && (
                                                <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
                                                    <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Counterfactual (Without Split)</div>
                                                    <div className="text-xl font-bold font-mono text-slate-900">
                                                        {advStats.insights.counterfactual.projected_yield?.toFixed(0)} <span className="text-xs text-slate-400">kg/ha projected</span>
                                                    </div>
                                                    <div className="text-xs text-slate-500 mt-0.5">
                                                        vs actual: {advStats.insights.counterfactual.actual_yield?.toFixed(0)} kg/ha
                                                    </div>
                                                    <div className="text-[10px] text-slate-400 mt-1">
                                                        Attribution: {advStats.insights.counterfactual.attribution_pct?.toFixed(1)}% attributable to split
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Timeline Chart */}
                                    {chartOption && (
                                        <div>
                                            <h4 className="text-xs font-bold text-slate-500 uppercase mb-3">Timeline Visualization</h4>
                                            <div className="h-[300px] bg-white border border-slate-200 rounded-lg p-3">
                                                <ReactECharts option={chartOption} style={{ height: '100%', width: '100%' }} />
                                            </div>
                                            <div className="flex items-center gap-2 mt-2 text-[10px] text-slate-400">
                                                <div className="w-4 h-0 border-t-2 border-dashed border-red-300"></div>
                                                <span>Split year: {selectedEvent.split_year}</span>
                                            </div>
                                        </div>
                                    )}

                                    {/* Warnings */}
                                    {advStats?.insights?.warnings && advStats.insights.warnings.length > 0 && (
                                        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                                            <div className="text-xs font-bold text-amber-700 mb-1 flex items-center gap-1">
                                                <AlertCircle size={12} /> Data Quality Notes
                                            </div>
                                            <ul className="text-xs text-amber-600 space-y-0.5 list-disc list-inside">
                                                {advStats.insights.warnings.map((w: string, i: number) => (
                                                    <li key={i}>{w}</li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}

                                    {/* Provenance */}
                                    {analysis?.provenance && (
                                        <div className="text-[10px] text-slate-400 pt-3 border-t border-slate-100 flex items-center justify-between">
                                            <span>Query: {analysis.provenance.query_hash?.slice(0, 20)}...</span>
                                            <span>Variable: {analysis.meta?.variable} | Mode: {analysis.meta?.mode}</span>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* ─── SECTION 4: ECONOMIC SPECIALIZATION ─── */}
                {generated && specData && selectedEvent && (
                    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden mt-6 animate-in">
                        <button
                            onClick={() => toggleSection('spec')}
                            className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-50 transition"
                        >
                            <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-lg bg-fuchsia-100 flex items-center justify-center">
                                    <PieChart size={16} className="text-fuchsia-600" />
                                </div>
                                <div className="text-left">
                                    <h3 className="text-sm font-bold text-slate-900">Section 4: Economic Specialization</h3>
                                    <p className="text-xs text-slate-500">Multi-crop matrix divergence (Parent vs Children)</p>
                                </div>
                            </div>
                            {expandedSections.spec ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                        </button>

                        {expandedSections.spec && (
                            <div className="px-5 pb-5 border-t border-slate-100 pt-4 grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div>
                                    <h4 className="text-xs font-bold text-slate-500 uppercase mb-3 text-center">Crop Mix Radar Comparison</h4>
                                    <div className="h-[350px] w-full">
                                        <ReactECharts option={radarOption!} style={{ height: '100%', width: '100%' }} />
                                    </div>
                                </div>

                                <div className="flex flex-col justify-center">
                                    <div className="bg-slate-50 border border-slate-200 rounded-xl p-5">
                                        <h4 className="text-sm font-bold text-slate-900 mb-4">Divergence Scores</h4>
                                        <p className="text-xs text-slate-500 mb-4">
                                            Measures how far the child&apos;s post-split crop portfolio drifted from the parent&apos;s pre-split portfolio. Higher Euclidean distance implies stronger agricultural specialization.
                                        </p>
                                        <div className="space-y-3">
                                            {Object.entries(specData.divergence_scores).map(([childName, score]) => (
                                                <div key={childName} className="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-lg">
                                                    <span className="font-semibold text-slate-800 text-sm">{childName}</span>
                                                    <div className="text-right">
                                                        <span className="font-mono font-bold text-fuchsia-700 text-lg">{score}</span>
                                                        <span className="text-[10px] text-slate-400 ml-1">pts</span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* ══════════════════ UNMAPPED DISTRICTS WARNING ══════════════════ */}
                {!loadingUnmapped && unmappedSplits && unmappedSplits.length > 0 && (
                    <div className="mt-12 bg-white border border-rose-200 rounded-xl shadow-sm overflow-hidden mb-8">
                        <div className="bg-rose-50 px-5 py-4 border-b border-rose-100 flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <AlertCircle className="text-rose-600" size={20} />
                                <div>
                                    <h3 className="text-sm font-bold text-slate-900">Data Integrity Warning: Unmapped Historical Districts</h3>
                                    <p className="text-xs text-slate-600 mt-0.5">
                                        The following {unmappedSplits.length} district lineages could not be mapped to modern LGD codes due to missing spelling aliases or colonial name changes.
                                        Splits originating from or resulting in these districts will have no metrics.
                                    </p>
                                </div>
                            </div>
                        </div>
                        <div className="p-0 overflow-x-auto max-h-[400px]">
                            <table className="text-xs w-full text-left border-collapse">
                                <thead className="bg-slate-50 sticky top-0 border-b border-slate-200 shadow-sm z-10">
                                    <tr>
                                        <th className="px-4 py-3 font-semibold text-slate-600">State</th>
                                        <th className="px-4 py-3 font-semibold text-slate-600">Historical District Name</th>
                                        <th className="px-4 py-3 font-semibold text-slate-600 w-24">Split Year</th>
                                        <th className="px-4 py-3 font-semibold text-slate-600 w-24">Role</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {unmappedSplits.map((item, idx) => (
                                        <tr key={idx} className="hover:bg-slate-50 transition">
                                            <td className="px-4 py-2.5 text-slate-700">{item.state}</td>
                                            <td className="px-4 py-2.5 font-medium text-slate-900">{item.district}</td>
                                            <td className="px-4 py-2.5 text-slate-500 font-mono">{item.year}</td>
                                            <td className="px-4 py-2.5">
                                                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${item.role === 'Parent' ? 'bg-indigo-50 text-indigo-700 border border-indigo-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                                    }`}>
                                                    {item.role}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>
        </main>
    );
}
