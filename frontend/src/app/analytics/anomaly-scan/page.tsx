'use client';

import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import { ApiError } from '../../services/api/client';
import { AINarrative } from '../../components/AINarrative';
import { ScanSearch, Activity, AlertTriangle, Info, Search, Bug, ShieldAlert } from 'lucide-react';
import ReactECharts from 'echarts-for-react';

export default function AnomalyScanPage() {
    const [cdk, setCdk] = useState('');
    const [selectedState, setSelectedState] = useState('');
    const [crop, setCrop] = useState('rice');
    const [searchInput, setSearchInput] = useState('');

    const { data: statesData } = useQuery({
        queryKey: ['states-list-anomaly'],
        queryFn: () => api.getStatesList(),
        staleTime: 3600000,
    });
    const states = useMemo(() => (statesData || []).map((s) => s.state).sort(), [statesData]);

    const { data: districtsData, isLoading: districtsLoading } = useQuery({
        queryKey: ['state-districts-anomaly', selectedState],
        queryFn: () => api.getDistrictsByState(selectedState),
        enabled: !!selectedState,
        staleTime: 3600000,
    });
    const districts = districtsData?.items || [];

    const { data, isLoading, isError, error } = useQuery({
        queryKey: ['anomalyScan', cdk, crop],
        queryFn: () => api.getAnomalyScan(cdk, crop),
        enabled: !!cdk,
        staleTime: 300_000,
        retry: 1,
    });

    const apiError = error instanceof ApiError ? error : null;
    const isNoDataError = !!apiError && [400, 404, 422].includes(apiError.status);
    const hasData = !!data && data.timeline?.length > 0;

    const chartOption = useMemo(() => {
        if (!hasData || !data) return null;

        const timelineData = data.timeline;
        const anomalyYears = new Set(data.anomalies.map(a => a.year));

        return {
            tooltip: {
                trigger: 'axis',
                formatter: (params: Array<{ axisValue: string; value: number; seriesName: string; marker: string }>) => {
                    const year = params[0]?.axisValue;
                    const isAnomaly = anomalyYears.has(Number(year));
                    let html = `<strong>${year}</strong>${isAnomaly ? ' <span style="color:#ef4444">⚠ Anomaly</span>' : ''}<br/>`;
                    for (const p of params) {
                        html += `${p.marker} ${p.seriesName}: <strong>${p.value.toLocaleString()}</strong> kg/ha<br/>`;
                    }
                    return html;
                },
            },
            legend: { data: ['Yield', 'Mean Yield'], bottom: 0, textStyle: { color: '#64748b' } },
            grid: { left: '5%', right: '5%', bottom: '15%', top: '10%', containLabel: true },
            xAxis: {
                type: 'category',
                data: timelineData.map(t => t.year),
                axisLabel: { color: '#64748b', rotate: 45 },
            },
            yAxis: {
                type: 'value',
                name: 'Yield (kg/ha)',
                nameTextStyle: { color: '#94a3b8' },
                splitLine: { lineStyle: { color: '#f1f5f9' } },
            },
            series: [
                {
                    name: 'Yield',
                    type: 'bar',
                    data: timelineData.map(t => ({
                        value: t.yield,
                        itemStyle: {
                            color: t.is_anomaly ? '#ef4444' : '#6366f1',
                            borderRadius: [4, 4, 0, 0],
                        },
                    })),
                    barMaxWidth: 28,
                },
                {
                    name: 'Mean Yield',
                    type: 'line',
                    data: timelineData.map(() => data.mean_yield),
                    lineStyle: { color: '#94a3b8', width: 1.5, type: 'dashed' },
                    itemStyle: { color: '#94a3b8' },
                    symbol: 'none',
                },
            ],
        };
    }, [data, hasData]);

    const getSeverityBadge = (score: number) => {
        if (score < -0.3) return { label: 'Severe', bg: 'bg-rose-100', text: 'text-rose-700' };
        if (score < -0.1) return { label: 'Moderate', bg: 'bg-amber-100', text: 'text-amber-700' };
        return { label: 'Mild', bg: 'bg-yellow-100', text: 'text-yellow-700' };
    };

    return (
        <main className="page-container">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center gap-4 mb-8 border-b border-slate-200 pb-6">
                <div className="p-3 bg-violet-100 text-violet-700 rounded-xl shadow-inner mt-1 shrink-0">
                    <ScanSearch size={24} />
                </div>
                <div>
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-violet-50 border border-violet-200 text-[10px] font-bold text-violet-700 uppercase tracking-widest mb-2">
                        <Bug size={10} /> Isolation Forest
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Anomaly Context Engine</h1>
                    <p className="text-sm text-slate-500 mt-1 max-w-3xl">
                        ML-powered anomaly detection using Isolation Forest to identify unusual year-over-year patterns
                        in yield, area, and production. AI explains <em>why</em> each anomaly may have occurred.
                    </p>
                </div>
            </div>

            {/* Controls */}
            <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6 shadow-sm">
                <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
                    <div className="md:col-span-3">
                        <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">State</label>
                        <select
                            value={selectedState}
                            onChange={(e) => {
                                setSelectedState(e.target.value);
                                setCdk('');
                                setSearchInput('');
                            }}
                            className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-violet-500 outline-none"
                        >
                            <option value="">Select state...</option>
                            {states.map((state) => (
                                <option key={state} value={state}>{state}</option>
                            ))}
                        </select>
                    </div>

                    <div className="md:col-span-5">
                        <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">District</label>
                        <select
                            value={cdk}
                            onChange={(e) => {
                                setCdk(e.target.value);
                                setSearchInput(e.target.value);
                            }}
                            disabled={!selectedState || districtsLoading}
                            className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-violet-500 outline-none disabled:opacity-60"
                        >
                            <option value="">
                                {!selectedState
                                    ? 'Select state first...'
                                    : districtsLoading
                                        ? 'Loading districts...'
                                        : 'Select district...'}
                            </option>
                            {districts.map((district) => (
                                <option key={district.cdk} value={district.cdk}>
                                    {district.name} ({district.cdk})
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="md:col-span-2">
                        <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Manual CDK</label>
                        <div className="flex gap-2">
                            <input
                                type="text"
                                value={searchInput}
                                onChange={e => setSearchInput(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && setCdk(searchInput.trim())}
                                placeholder="LGD code"
                                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-violet-500 outline-none font-mono"
                            />
                            <button onClick={() => setCdk(searchInput.trim())} className="px-3 py-2 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700 transition-colors">
                                <Search size={16} />
                            </button>
                        </div>
                    </div>

                    <div className="md:col-span-2">
                        <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Crop</label>
                        <select value={crop} onChange={e => setCrop(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-violet-500 outline-none">
                            {['rice', 'wheat', 'cotton', 'sugarcane', 'maize', 'groundnut', 'sorghum', 'chickpea', 'soyabean'].map(c => (
                                <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                            ))}
                        </select>
                    </div>
                </div>
            </div>

            {/* Loading */}
            {isLoading && (
                <div className="flex items-center justify-center py-20 bg-white border border-slate-200 rounded-xl">
                    <div className="w-8 h-8 border-2 border-violet-200 border-t-violet-600 rounded-full animate-spin mr-3" />
                    <span className="text-sm text-slate-500 font-medium">Running Isolation Forest anomaly scan...</span>
                </div>
            )}

            {/* Error */}
            {isError && !isNoDataError && (
                <div className="bg-white border border-rose-200 rounded-xl p-10 text-center shadow-sm">
                    <AlertTriangle size={36} className="mx-auto mb-3 text-rose-400" />
                    <h3 className="text-lg font-bold text-slate-700">Analysis Failed</h3>
                    <p className="text-sm text-slate-500 mt-1">{(error as Error)?.message || 'Could not run anomaly scan.'}</p>
                </div>
            )}

            {/* No data */}
            {!isLoading && cdk && !hasData && (!isError || isNoDataError) && (
                <div className="bg-white border border-slate-200 rounded-xl p-10 text-center shadow-sm">
                    <Info size={36} className="mx-auto mb-3 text-slate-300" />
                    <h3 className="text-lg font-bold text-slate-700">Insufficient Data</h3>
                    <p className="text-sm text-slate-500 mt-1">{apiError?.message || 'Need at least 8 years of data for anomaly detection.'}</p>
                </div>
            )}

            {/* Results */}
            {hasData && data && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {/* Summary cards */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Years Analyzed</div>
                            <div className="text-2xl font-bold font-mono text-slate-700">{data.years_analyzed}</div>
                            <div className="text-xs text-slate-500 mt-1">{data.period}</div>
                        </div>
                        <div className={`border rounded-xl p-5 shadow-sm ${data.total_anomalies > 0 ? 'bg-rose-50 border-rose-200' : 'bg-emerald-50 border-emerald-200'}`}>
                            <div className={`text-[10px] uppercase font-bold mb-1 ${data.total_anomalies > 0 ? 'text-rose-600/70' : 'text-emerald-600/70'}`}>Anomalies Detected</div>
                            <div className={`text-2xl font-bold font-mono ${data.total_anomalies > 0 ? 'text-rose-700' : 'text-emerald-700'}`}>{data.total_anomalies}</div>
                            <div className="text-xs text-slate-500 mt-1">via Isolation Forest</div>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Mean Yield</div>
                            <div className="text-2xl font-bold font-mono text-indigo-600">{data.mean_yield.toLocaleString()}</div>
                            <div className="text-xs text-slate-500 mt-1">kg/ha baseline</div>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">District</div>
                            <div className="text-lg font-bold text-slate-800 truncate">{data.name}</div>
                            <div className="text-xs text-slate-500 mt-1">{data.state}</div>
                        </div>
                    </div>

                    <AINarrative narrative={data.ai_narrative} />

                    {/* Warnings */}
                    {data.warnings && data.warnings.length > 0 && (
                        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800 shadow-sm">
                            <strong className="flex items-center gap-1.5 mb-1"><AlertTriangle size={14} /> Notes:</strong>
                            <ul className="list-disc list-inside space-y-0.5 text-xs mt-1">
                                {data.warnings.map((w, i) => <li key={i}>{w}</li>)}
                            </ul>
                        </div>
                    )}

                    {/* Timeline Chart */}
                    {chartOption && (
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <h2 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
                                <Activity size={16} className="text-violet-600" /> Yield Timeline — Anomalies Highlighted
                            </h2>
                            <div className="h-[350px]">
                                <ReactECharts option={chartOption} style={{ height: '100%', width: '100%' }} />
                            </div>
                            <p className="text-xs text-slate-400 mt-2">
                                Red bars indicate years flagged as multivariate anomalies by the Isolation Forest model.
                            </p>
                        </div>
                    )}

                    {/* Anomaly Detail Cards */}
                    {data.anomalies.length > 0 && (
                        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                            <div className="p-4 border-b border-slate-200 bg-slate-50">
                                <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                                    <ShieldAlert size={16} className="text-rose-500" /> Detected Anomalies
                                </h2>
                            </div>
                            <div className="divide-y divide-slate-100">
                                {data.anomalies.map((a, i) => {
                                    const severity = getSeverityBadge(a.anomaly_score);
                                    return (
                                        <div key={i} className="p-4 hover:bg-slate-50/50 transition-colors">
                                            <div className="flex items-start gap-3">
                                                <div className="font-mono text-lg font-bold text-slate-700 w-14 shrink-0">{a.year}</div>
                                                <div className="flex-1">
                                                    <div className="flex flex-wrap gap-2 mb-2">
                                                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${severity.bg} ${severity.text}`}>
                                                            <ShieldAlert size={10} /> {severity.label}
                                                        </span>
                                                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-600">
                                                            Score: {a.anomaly_score.toFixed(3)}
                                                        </span>
                                                        {a.features_used.map((f, j) => (
                                                            <span key={j} className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-violet-50 text-violet-600 border border-violet-200">
                                                                {f}
                                                            </span>
                                                        ))}
                                                    </div>
                                                    <p className="text-xs text-slate-500">{a.details}</p>
                                                </div>
                                                <div className="text-right shrink-0">
                                                    <div className="text-lg font-bold font-mono text-slate-700">{a.yield_value.toLocaleString()}</div>
                                                    <div className={`text-xs font-bold ${a.yield_deviation_pct < 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                                                        {a.yield_deviation_pct > 0 ? '+' : ''}{a.yield_deviation_pct.toFixed(1)}%
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </main>
    );
}
