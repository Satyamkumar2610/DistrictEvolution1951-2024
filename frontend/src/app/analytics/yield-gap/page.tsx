'use client';

import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import { Activity, Target, TrendingUp, Maximize2, Minimize2, Info } from 'lucide-react';
import ReactECharts from 'echarts-for-react';

import type { YieldGapDistrictRanking } from '../../services/api';

interface StateSelectOption {
    value: string;
    label: string;
}

export default function YieldGapPage() {
    const [selectedState, setSelectedState] = useState('');
    const [selectedCrop, setSelectedCrop] = useState('wheat');
    const [yearRange, setYearRange] = useState('2000-2020');

    const startYear = parseInt(yearRange.split('-')[0]);
    const endYear = parseInt(yearRange.split('-')[1]);

    // Queries
    const { data: summaryData } = useQuery({ queryKey: ['stateSummary'], queryFn: api.getSummary, staleTime: 3600000 });
    const states = useMemo<StateSelectOption[]>(() => {
        if (!summaryData?.states) return [];
        const values = Array.isArray(summaryData.states)
            ? summaryData.states
            : Object.keys(summaryData.states).sort();
        return values.map((value) => ({ value, label: value }));
    }, [summaryData]);

    const { data: gapData, isLoading, isError } = useQuery({
        queryKey: ['yieldGap', selectedState, selectedCrop, startYear, endYear],
        queryFn: () => api.getYieldGap(selectedState, selectedCrop, startYear, endYear),
        enabled: !!selectedState,
    });

    const hasData = !!gapData && gapData.district_rankings?.length > 0;

    // Chart Configuration
    const timelineOption = useMemo(() => {
        if (!hasData) return null;

        return {
            title: { text: 'Agri-Yield Convergence Timeline', textStyle: { fontSize: 13, color: '#475569' } },
            tooltip: { trigger: 'axis' },
            legend: { data: ['90th Percentile Frontier', 'State Average', 'Average Gap'], bottom: 0 },
            grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
            xAxis: {
                type: 'category',
                boundaryGap: false,
                data: gapData.convergence_timeline.map((point) => point.year)
            },
            yAxis: [
                {
                    type: 'value',
                    name: 'Yield (kg/ha)',
                    position: 'left',
                    splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } }
                }
            ],
            series: [
                {
                    name: '90th Percentile Frontier',
                    type: 'line',
                    data: gapData.convergence_timeline.map((point) => point.frontier_yield),
                    itemStyle: { color: '#8b5cf6' }, // Violet
                    lineStyle: { width: 3 },
                    smooth: true,
                    areaStyle: {
                        color: {
                            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                            colorStops: [{ offset: 0, color: 'rgba(139, 92, 246, 0.2)' }, { offset: 1, color: 'rgba(139, 92, 246, 0)' }]
                        }
                    }
                },
                {
                    name: 'State Average',
                    type: 'line',
                    data: gapData.convergence_timeline.map((point) => point.state_avg_yield),
                    itemStyle: { color: '#10b981' }, // Emerald
                    lineStyle: { width: 3, type: 'dashed' },
                    smooth: true
                },
                {
                    name: 'Average Gap',
                    type: 'bar',
                    data: gapData.convergence_timeline.map((point) => point.avg_gap),
                    itemStyle: { color: '#f59e0b', opacity: 0.6 }, // Amber
                    barMaxWidth: 30
                }
            ]
        };
    }, [gapData, hasData]);

    // Analytics Compute
    const stats = useMemo(() => {
        if (!hasData) return null;
        const ranks = gapData.district_rankings;
        const totalDistricts = ranks.length;
        const closingCount = ranks.filter((ranking) => ranking.status === 'Closing').length;
        const wideningCount = ranks.filter((ranking) => ranking.status === 'Widening').length;

        const firstYear = gapData.convergence_timeline[0];
        const lastYear = gapData.convergence_timeline[gapData.convergence_timeline.length - 1];
        const gapReduction = firstYear.avg_gap - lastYear.avg_gap;
        const gapReductionPct = (gapReduction / firstYear.avg_gap) * 100;

        return { closingCount, wideningCount, totalDistricts, gapReductionPct, lastYearGap: lastYear.avg_gap };
    }, [gapData, hasData]);

    return (
        <main className="page-container">

            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center gap-4 mb-8 border-b border-slate-200 pb-6">
                <div className="p-3 bg-fuchsia-100 text-fuchsia-700 rounded-xl shadow-inner mt-1 shrink-0">
                    <Target size={24} />
                </div>
                <div>
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-fuchsia-50 border border-fuchsia-200 text-[10px] font-bold text-fuchsia-700 uppercase tracking-widest mb-2">
                        <Activity size={10} /> Productivity Potential
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Yield Gap Mapping</h1>
                    <p className="text-sm text-slate-500 mt-1 max-w-3xl">
                        Measures the untapped agricultural potential by calculating the difference between a district&apos;s actual yield and the state&apos;s 90th percentile &quot;Frontier Yield&quot;. Plots long-term convergence trends.
                    </p>
                </div>
            </div>

            {/* Configuration Panel */}
            <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6 shadow-sm flex flex-col sm:flex-row gap-4 items-end">
                <div className="flex-1">
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">State</label>
                    <select
                        value={selectedState}
                        onChange={(e) => setSelectedState(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
                    >
                        <option value="">Select state...</option>
                        {states.map((state) => <option key={state.value} value={state.value}>{state.label}</option>)}
                    </select>
                </div>

                <div className="w-40">
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Crop</label>
                    <select
                        value={selectedCrop}
                        onChange={(e) => setSelectedCrop(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-fuchsia-500 outline-none"
                    >
                        {['wheat', 'rice', 'cotton', 'sugarcane', 'maize', 'groundnut'].map(c => (
                            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                        ))}
                    </select>
                </div>

                <div className="w-48">
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Analysis Window</label>
                    <select
                        value={yearRange}
                        onChange={(e) => setYearRange(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-fuchsia-500 outline-none"
                    >
                        {['2000-2020', '1990-2010', '1980-2000', '1970-1990'].map(y => (
                            <option key={y} value={y}>{y}</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Loading / No Data State */}
            {isLoading && (
                <div className="flex items-center justify-center py-20 bg-white border border-slate-200 rounded-xl">
                    <div className="w-8 h-8 border-2 border-fuchsia-200 border-t-fuchsia-600 rounded-full animate-spin mr-3" />
                    <span className="text-sm text-slate-500 font-medium">Computing frontier yields...</span>
                </div>
            )}

            {/* Error State */}
            {isError && (
                <div className="bg-white border border-rose-200 rounded-xl p-10 text-center shadow-sm">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-rose-50 flex items-center justify-center">
                        <Target size={24} className="text-rose-400" />
                    </div>
                    <h3 className="text-lg font-bold text-slate-700">Failed to Load Data</h3>
                    <p className="text-sm text-slate-500 mt-1">The server returned an error. Please try a different selection or refresh.</p>
                </div>
            )}

            {!isLoading && !isError && selectedState && !hasData && (
                <div className="bg-white border border-slate-200 rounded-xl p-10 text-center shadow-sm">
                    <Info size={36} className="mx-auto mb-3 text-slate-300" />
                    <h3 className="text-lg font-bold text-slate-700">No Productivity Data Available</h3>
                    <p className="text-sm text-slate-500 mt-1">Unable to compute frontier yields for this crop and period.</p>
                </div>
            )}

            {/* Results Dashboard */}
            {hasData && stats && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {/* Summary Metrics */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Convergence Trajectory</div>
                            <div className={`text-2xl font-bold font-mono ${stats.gapReductionPct > 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                                {stats.gapReductionPct > 0 ? '+' : ''}{stats.gapReductionPct.toFixed(1)}%
                            </div>
                            <div className="text-xs text-slate-500 mt-1">{stats.gapReductionPct > 0 ? 'Reduction in average gap' : 'Increase in average gap'}</div>
                        </div>

                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Statewide Avg Gap</div>
                            <div className="text-2xl font-bold font-mono text-amber-600">{Math.round(stats.lastYearGap)} <span className="text-sm sans text-slate-500">kg/ha</span></div>
                            <div className="text-xs text-slate-500 mt-1">Current untapped potential</div>
                        </div>

                        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-emerald-800/60 mb-1">Closing The Gap</div>
                            <div className="text-2xl font-bold font-mono text-emerald-700">{stats.closingCount} <span className="text-sm sans text-emerald-600/70">/ {stats.totalDistricts}</span></div>
                            <div className="text-xs text-emerald-600/80 mt-1">Districts catching up to frontier</div>
                        </div>

                        <div className="bg-rose-50 border border-rose-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-rose-800/60 mb-1">Falling Behind</div>
                            <div className="text-2xl font-bold font-mono text-rose-700">{stats.wideningCount} <span className="text-sm sans text-rose-600/70">/ {stats.totalDistricts}</span></div>
                            <div className="text-xs text-rose-600/80 mt-1">Districts dropping from frontier</div>
                        </div>
                    </div>

                    {/* Chart Row */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Line Chart */}
                        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <h2 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2"><TrendingUp size={16} className="text-fuchsia-600" /> State Convergence Timeline</h2>
                            <div className="h-[400px] w-full relative">
                                <ReactECharts option={timelineOption!} style={{ height: '100%', width: '100%' }} />
                            </div>
                        </div>

                        {/* Table */}
                        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col h-[470px]">
                            <div className="p-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
                                <h2 className="text-sm font-bold text-slate-900">Highest Yield Gaps</h2>
                                <span className="text-[10px] uppercase font-bold text-amber-600 bg-amber-100 px-2 py-0.5 rounded">Needs Intervention</span>
                            </div>
                            <div className="flex-1 overflow-y-auto">
                                <table className="w-full text-left text-sm">
                                    <thead className="bg-white sticky top-0 border-b border-slate-100 shadow-sm z-10">
                                        <tr className="text-xs uppercase text-slate-400">
                                            <th className="py-2 px-4 font-semibold">District</th>
                                            <th className="py-2 px-4 font-semibold text-right">Avg Gap</th>
                                            <th className="py-2 px-4 font-semibold text-center">Trend</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-50">
                                        {gapData.district_rankings.map((district: YieldGapDistrictRanking) => (
                                            <tr key={district.cdk} className="hover:bg-slate-50/80 transition-colors">
                                                <td className="py-3 px-4">
                                                    <div className="font-medium text-slate-800">{district.district_name}</div>
                                                    <div className="text-[10px] text-slate-400">Yield: {Math.round(district.avg_yield)} kg/ha</div>
                                                </td>
                                                <td className="py-3 px-4 text-right font-mono text-amber-600 font-bold">
                                                    {Math.round(district.avg_gap)}
                                                </td>
                                                <td className="py-3 px-4 text-center">
                                                    {district.status === 'Closing' ? (
                                                        <div className="inline-flex items-center text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded" title="Gap is narrowing">
                                                            <Minimize2 size={12} />
                                                        </div>
                                                    ) : district.status === 'Widening' ? (
                                                        <div className="inline-flex items-center text-rose-600 bg-rose-50 px-1.5 py-0.5 rounded" title="Gap is widening">
                                                            <Maximize2 size={12} />
                                                        </div>
                                                    ) : (
                                                        <div className="inline-flex items-center text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded" title="Stagnant">
                                                            —
                                                        </div>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </main>
    )
}
