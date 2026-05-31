'use client';

import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import { ApiError } from '../../services/api/client';
import { AINarrative } from '../../components/AINarrative';
import { CloudLightning, AlertTriangle, Activity, Flame, Droplets, Snowflake, HelpCircle, Info, Search } from 'lucide-react';
import ReactECharts from 'echarts-for-react';

const EVENT_ICONS: Record<string, { icon: React.ReactNode; color: string; bg: string }> = {
    drought: { icon: <Droplets size={14} />, color: 'text-amber-700', bg: 'bg-amber-100' },
    flood: { icon: <CloudLightning size={14} />, color: 'text-blue-700', bg: 'bg-blue-100' },
    heat_wave: { icon: <Flame size={14} />, color: 'text-rose-700', bg: 'bg-rose-100' },
    cold_wave: { icon: <Snowflake size={14} />, color: 'text-cyan-700', bg: 'bg-cyan-100' },
    unknown: { icon: <HelpCircle size={14} />, color: 'text-slate-500', bg: 'bg-slate-100' },
};

export default function ClimateShocksPage() {
    const [cdk, setCdk] = useState('');
    const [selectedState, setSelectedState] = useState('');
    const [crop, setCrop] = useState('rice');
    const [searchInput, setSearchInput] = useState('');

    const { data: summaryData } = useQuery({
        queryKey: ['stateSummary'],
        queryFn: api.getSummary,
        staleTime: 3600000,
    });
    const states = useMemo(() => {
        if (!summaryData?.states) return [];
        return (Array.isArray(summaryData.states) ? summaryData.states : Object.keys(summaryData.states)).sort();
    }, [summaryData]);

    const { data: districtsData, isLoading: districtsLoading } = useQuery({
        queryKey: ['state-districts-intelligence', selectedState],
        queryFn: () => api.getDistrictsByState(selectedState),
        enabled: !!selectedState,
        staleTime: 3600000,
    });
    const districts = districtsData?.items || [];

    const { data, isLoading, isError, error } = useQuery({
        queryKey: ['climateShocks', cdk, crop],
        queryFn: () => api.getClimateShocks(cdk, crop),
        enabled: !!cdk,
        staleTime: 300_000,
        retry: 1,
    });

    const apiError = error instanceof ApiError ? error : null;
    const isNoDataError = !!apiError && [400, 404, 422].includes(apiError.status);
    const hasData = !!data && data.attributions?.length > 0;

    const chartOption = useMemo(() => {
        if (!hasData) return null;
        return {
            tooltip: { trigger: 'axis' },
            legend: { data: ['Actual Yield', 'Expected Yield'], bottom: 0, textStyle: { color: '#64748b' } },
            grid: { left: '5%', right: '5%', bottom: '15%', top: '10%', containLabel: true },
            xAxis: { type: 'category', data: data.attributions.map(a => a.year), axisLabel: { color: '#64748b' } },
            yAxis: { type: 'value', name: 'Yield (kg/ha)', nameTextStyle: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#f1f5f9' } } },
            series: [
                {
                    name: 'Actual Yield', type: 'bar',
                    data: data.attributions.map(a => ({
                        value: a.actual_yield,
                        itemStyle: { color: a.z_score < -2 ? '#ef4444' : '#f97316', borderRadius: [4, 4, 0, 0] }
                    })),
                    barMaxWidth: 32,
                },
                {
                    name: 'Expected Yield', type: 'line', smooth: true,
                    data: data.attributions.map(a => a.expected_yield),
                    lineStyle: { color: '#6366f1', width: 2, type: 'dashed' },
                    itemStyle: { color: '#6366f1' },
                    symbol: 'circle', symbolSize: 6,
                },
            ],
        };
    }, [data, hasData]);

    return (
        <main className="page-container">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center gap-4 mb-8 border-b border-slate-200 pb-6">
                <div className="p-3 bg-orange-100 text-orange-700 rounded-xl shadow-inner mt-1 shrink-0">
                    <CloudLightning size={24} />
                </div>
                <div>
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-orange-50 border border-orange-200 text-[10px] font-bold text-orange-700 uppercase tracking-widest mb-2">
                        <Activity size={10} /> Phase 3 Intelligence
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Climate Shock Atlas</h1>
                    <p className="text-sm text-slate-500 mt-1 max-w-3xl">
                        Automatically detects abnormal yield drops and attributes them to concurrent climatic events &mdash;
                        drought (SPI), floods, heat waves, cold waves. Reveals which climate hazards hurt which crops most.
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
                            className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-orange-500 outline-none"
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
                            className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-orange-500 outline-none disabled:opacity-60"
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
                                placeholder="UP_agra_1981"
                                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-orange-500 outline-none font-mono"
                            />
                            <button onClick={() => setCdk(searchInput.trim())} className="px-3 py-2 bg-orange-600 text-white rounded-lg text-sm font-medium hover:bg-orange-700 transition-colors">
                                <Search size={16} />
                            </button>
                        </div>
                    </div>

                    <div className="md:col-span-2">
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Crop</label>
                    <select value={crop} onChange={e => setCrop(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-orange-500 outline-none">
                        {['rice', 'wheat', 'cotton', 'sugarcane', 'maize', 'groundnut', 'sorghum', 'chickpea', 'soyabean'].map(c => (
                            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                        ))}
                    </select>
                </div>
                </div>
                <p className="text-xs text-slate-500 mt-3">
                    Select State and District from dropdowns for easiest use. Manual CDK entry is optional.
                </p>
            </div>

            {/* States */}
            {isLoading && (
                <div className="flex items-center justify-center py-20 bg-white border border-slate-200 rounded-xl">
                    <div className="w-8 h-8 border-2 border-orange-200 border-t-orange-600 rounded-full animate-spin mr-3" />
                    <span className="text-sm text-slate-500 font-medium">Analyzing climate shocks...</span>
                </div>
            )}

            {isError && !isNoDataError && (
                <div className="bg-white border border-rose-200 rounded-xl p-10 text-center shadow-sm">
                    <AlertTriangle size={36} className="mx-auto mb-3 text-rose-400" />
                    <h3 className="text-lg font-bold text-slate-700">Analysis Failed</h3>
                    <p className="text-sm text-slate-500 mt-1">{(error as Error)?.message || 'Could not retrieve climate shock data.'}</p>
                </div>
            )}

            {!isLoading && cdk && !hasData && (!isError || isNoDataError) && (
                <div className="bg-white border border-slate-200 rounded-xl p-10 text-center shadow-sm">
                    <Info size={36} className="mx-auto mb-3 text-slate-300" />
                    <h3 className="text-lg font-bold text-slate-700">No Shocks Detected</h3>
                    <p className="text-sm text-slate-500 mt-1">{apiError?.message || 'Either no significant yield drops occurred, or climate data is unavailable.'}</p>
                </div>
            )}

            {/* Initial state — nothing selected */}
            {!isLoading && !cdk && !isError && (
                <div className="bg-white border border-dashed border-slate-300 rounded-xl p-10 text-center shadow-sm">
                    <CloudLightning size={48} className="mx-auto mb-4 text-orange-300" />
                    <h3 className="text-lg font-bold text-slate-700">Select a District to Analyze</h3>
                    <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
                        Choose a state and district from the dropdowns above, or enter a CDK code manually to detect climate shocks and yield loss attributions.
                    </p>
                </div>
            )}

            {/* Results */}
            {hasData && data && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {/* Summary cards */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Shock Years</div>
                            <div className="text-2xl font-bold font-mono text-rose-600">{data.total_shock_years}</div>
                            <div className="text-xs text-slate-500 mt-1">Years with Z-score &lt; -1.5</div>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Avg Loss per Shock</div>
                            <div className="text-2xl font-bold font-mono text-amber-600">{Math.abs(data.avg_loss_per_shock_pct).toFixed(1)}%</div>
                            <div className="text-xs text-slate-500 mt-1">Mean yield drop during shocks</div>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Analysis Period</div>
                            <div className="text-2xl font-bold font-mono text-slate-700">{data.period}</div>
                            <div className="text-xs text-slate-500 mt-1">Years with overlapping data</div>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Primary Hazard</div>
                            <div className="text-xl font-bold text-slate-800 capitalize">{data.most_damaging_event_type?.replace('_', ' ') || 'None'}</div>
                            <div className="text-xs text-slate-500 mt-1">Most frequent shock cause</div>
                        </div>
                    </div>

                    <AINarrative narrative={data.ai_narrative} />

                    {/* Warnings */}
                    {data.warnings && data.warnings.length > 0 && (
                        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800 shadow-sm">
                            <strong className="flex items-center gap-1.5 mb-1"><AlertTriangle size={14} /> Data Notes:</strong>
                            <ul className="list-disc list-inside space-y-0.5 text-xs mt-1">
                                {data.warnings.map((w, i) => <li key={i}>{w}</li>)}
                            </ul>
                        </div>
                    )}

                    {/* Chart */}
                    {chartOption && (
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <h2 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
                                <Activity size={16} className="text-orange-600" /> Yield Shock Timeline
                            </h2>
                            <div className="h-[350px]">
                                <ReactECharts option={chartOption} style={{ height: '100%', width: '100%' }} />
                            </div>
                        </div>
                    )}

                    {/* Attribution cards */}
                    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                        <div className="p-4 border-b border-slate-200 bg-slate-50">
                            <h2 className="text-sm font-bold text-slate-900">Shock Attributions</h2>
                        </div>
                        <div className="divide-y divide-slate-100">
                            {data.attributions.map((a, i) => (
                                <div key={i} className="p-4 hover:bg-slate-50/50 transition-colors">
                                    <div className="flex items-start gap-3">
                                        <div className="font-mono text-lg font-bold text-slate-700 w-14 shrink-0">{a.year}</div>
                                        <div className="flex-1">
                                            <div className="flex flex-wrap gap-2 mb-2">
                                                {a.attributed_events.map((e, j) => {
                                                    const ev = EVENT_ICONS[e.type] || EVENT_ICONS.unknown;
                                                    return (
                                                        <span key={j} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${ev.bg} ${ev.color}`}>
                                                            {ev.icon} {e.type.replace('_', ' ')} ({e.severity})
                                                        </span>
                                                    );
                                                })}
                                            </div>
                                            <p className="text-xs text-slate-500">{a.interpretation}</p>
                                        </div>
                                        <div className="text-right shrink-0">
                                            <div className="text-lg font-bold font-mono text-rose-600">{a.deviation_pct.toFixed(1)}%</div>
                                            <div className="text-[10px] text-slate-400">Confidence: {(a.confidence * 100).toFixed(0)}%</div>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </main>
    );
}
