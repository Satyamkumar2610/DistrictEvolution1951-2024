'use client';

import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import { ApiError } from '../../services/api/client';
import { FlaskConical, Activity, TrendingUp, Info, AlertTriangle } from 'lucide-react';
import ReactECharts from 'echarts-for-react';

export default function YieldFrontierPage() {
    const [selectedState, setSelectedState] = useState('');
    const [selectedCrop, setSelectedCrop] = useState('rice');
    const [selectedYear, setSelectedYear] = useState(2015);

    const { data: summaryData } = useQuery({ queryKey: ['stateSummary'], queryFn: api.getSummary, staleTime: 3600000 });
    const states = useMemo(() => {
        if (!summaryData?.states) return [];
        return (Array.isArray(summaryData.states) ? summaryData.states : Object.keys(summaryData.states)).sort();
    }, [summaryData]);

    const { data, isLoading, isError, error } = useQuery({
        queryKey: ['yieldFrontier', selectedState, selectedCrop, selectedYear],
        queryFn: () => api.getYieldFrontier(selectedState, selectedCrop, selectedYear),
        enabled: !!selectedState,
    });

    const apiError = error instanceof ApiError ? error : null;
    const isNoDataError = !!apiError && [400, 404, 422].includes(apiError.status);
    const hasData = !!data && data.district_results?.length > 0;

    const chartOption = useMemo(() => {
        if (!hasData) return null;
        const sorted = [...data.district_results].sort((a, b) => a.technical_efficiency - b.technical_efficiency);
        return {
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                formatter: (params: Array<{ name: string; value: number; seriesName: string }>) => {
                    const d = sorted.find(x => x.name === params[0].name);
                    if (!d) return '';
                    return `<div class="font-bold">${d.name}</div>
                        <div class="text-xs mt-1">TE: <b>${(d.technical_efficiency * 100).toFixed(1)}%</b></div>
                        <div class="text-xs">Actual: <b>${Math.round(d.observed_yield)}</b> kg/ha</div>
                        <div class="text-xs">Frontier: <b>${Math.round(d.frontier_yield)}</b> kg/ha</div>
                        <div class="text-xs">Gap: <b>${d.yield_gap_pct.toFixed(1)}%</b></div>`;
                },
            },
            grid: { left: '3%', right: '5%', bottom: '22%', top: '5%', containLabel: true },
            xAxis: {
                type: 'category', data: sorted.map(d => d.name),
                axisLabel: { rotate: 45, fontSize: 10, color: '#64748b', interval: 0, overflow: 'truncate', width: 60 },
            },
            yAxis: { type: 'value', name: 'Yield (kg/ha)', splitLine: { lineStyle: { color: '#f1f5f9' } } },
            series: [
                {
                    name: 'Observed Yield', type: 'bar', stack: 'total',
                    data: sorted.map(d => ({
                        value: d.observed_yield,
                        itemStyle: {
                            color: d.technical_efficiency >= 0.8 ? '#10b981' : d.technical_efficiency >= 0.6 ? '#f59e0b' : '#ef4444',
                            borderRadius: [0, 0, 0, 0],
                        },
                    })),
                    barMaxWidth: 24,
                },
                {
                    name: 'Yield Gap', type: 'bar', stack: 'total',
                    data: sorted.map(d => ({
                        value: Math.max(0, d.frontier_yield - d.observed_yield),
                        itemStyle: { color: 'rgba(148, 163, 184, 0.2)', borderColor: '#cbd5e1', borderWidth: 1, borderType: 'dashed', borderRadius: [4, 4, 0, 0] },
                    })),
                    barMaxWidth: 24,
                },
            ],
        };
    }, [data, hasData]);

    return (
        <main className="page-container">
            <div className="flex flex-col md:flex-row md:items-center gap-4 mb-8 border-b border-slate-200 pb-6">
                <div className="p-3 bg-violet-100 text-violet-700 rounded-xl shadow-inner mt-1 shrink-0">
                    <FlaskConical size={24} />
                </div>
                <div>
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-violet-50 border border-violet-200 text-[10px] font-bold text-violet-700 uppercase tracking-widest mb-2">
                        <Activity size={10} /> Stochastic Frontier Analysis
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Yield Frontier &amp; Technical Efficiency</h1>
                    <p className="text-sm text-slate-500 mt-1 max-w-3xl">
                        Replaces the static P90 ceiling with an econometric <strong>Stochastic Frontier Model</strong> that
                        estimates the maximum achievable yield and each district&apos;s <strong>Technical Efficiency</strong> (0-100%).
                    </p>
                </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6 shadow-sm flex flex-col sm:flex-row gap-4 items-end">
                <div className="flex-1">
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">State</label>
                    <select value={selectedState} onChange={e => setSelectedState(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-violet-500 outline-none">
                        <option value="">Select state...</option>
                        {states.map(s => <option key={s as string} value={s as string}>{s as string}</option>)}
                    </select>
                </div>
                <div className="w-40">
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Crop</label>
                    <select value={selectedCrop} onChange={e => setSelectedCrop(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-violet-500 outline-none">
                        {['rice', 'wheat', 'cotton', 'sugarcane', 'maize', 'groundnut'].map(c => (
                            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                        ))}
                    </select>
                </div>
                <div className="w-32">
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Year</label>
                    <select value={selectedYear} onChange={e => setSelectedYear(Number(e.target.value))} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-violet-500 outline-none">
                        {[2020, 2017, 2015, 2010, 2005, 2000].map(y => <option key={y} value={y}>{y}</option>)}
                    </select>
                </div>
            </div>

            {isLoading && (
                <div className="flex items-center justify-center py-20 bg-white border border-slate-200 rounded-xl">
                    <div className="w-8 h-8 border-2 border-violet-200 border-t-violet-600 rounded-full animate-spin mr-3" />
                    <span className="text-sm text-slate-500 font-medium">Estimating production frontier...</span>
                </div>
            )}
            {isError && !isNoDataError && (
                <div className="bg-white border border-rose-200 rounded-xl p-10 text-center shadow-sm">
                    <AlertTriangle size={36} className="mx-auto mb-3 text-rose-400" />
                    <h3 className="text-lg font-bold text-slate-700">Frontier Estimation Failed</h3>
                    <p className="text-sm text-slate-500 mt-1">{(error as Error)?.message || 'Insufficient district data or model did not converge.'}</p>
                </div>
            )}
            {!isLoading && selectedState && !hasData && (!isError || isNoDataError) && (
                <div className="bg-white border border-slate-200 rounded-xl p-10 text-center shadow-sm">
                    <Info size={36} className="mx-auto mb-3 text-slate-300" />
                    <h3 className="text-lg font-bold text-slate-700">No Data Available</h3>
                    <p className="text-sm text-slate-500 mt-1">{apiError?.message || 'Not enough district observations for the selected state/crop/year.'}</p>
                </div>
            )}

            {hasData && data && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Mean Efficiency</div>
                            <div className="text-2xl font-bold font-mono text-violet-600">{(data.model_stats.mean_te * 100).toFixed(1)}%</div>
                            <div className="text-xs text-slate-500 mt-1">Average technical efficiency</div>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Gamma (γ)</div>
                            <div className="text-2xl font-bold font-mono text-slate-700">{(data.model_stats.gamma * 100).toFixed(1)}%</div>
                            <div className="text-xs text-slate-500 mt-1">Variance from inefficiency</div>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Districts</div>
                            <div className="text-2xl font-bold font-mono text-slate-700">{data.model_stats.n_districts}</div>
                            <div className="text-xs text-slate-500 mt-1">In the SFA model</div>
                        </div>
                        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-emerald-700/70 mb-1">Most Efficient</div>
                            <div className="text-lg font-bold text-emerald-800 truncate">{data.district_results[0]?.name}</div>
                            <div className="text-xs text-emerald-600 mt-1">TE: {(data.district_results[0]?.technical_efficiency * 100).toFixed(1)}%</div>
                        </div>
                    </div>

                    {chartOption && (
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <h2 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
                                <TrendingUp size={16} className="text-violet-600" /> District Efficiency Ranking
                            </h2>
                            <div className="h-[400px]">
                                <ReactECharts option={chartOption} style={{ height: '100%', width: '100%' }} />
                            </div>
                            <div className="flex gap-4 mt-3 justify-center text-xs text-slate-500">
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500" /> TE ≥ 80%</span>
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-500" /> TE 60-79%</span>
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500" /> TE &lt; 60%</span>
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded border border-slate-300 bg-slate-100" /> Yield Gap</span>
                            </div>
                        </div>
                    )}

                    <div className="bg-white border border-indigo-100 rounded-xl p-4 text-sm text-indigo-800 shadow-sm">
                        <strong>Model Interpretation:</strong> {data.frontier_interpretation}
                    </div>

                    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                        <div className="p-4 border-b border-slate-200 bg-slate-50">
                            <h2 className="text-sm font-bold text-slate-900">District Rankings by Technical Efficiency</h2>
                        </div>
                        <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
                            <table className="w-full text-left text-sm">
                                <thead className="bg-white sticky top-0 border-b border-slate-200 z-10">
                                    <tr className="text-xs uppercase text-slate-400">
                                        <th className="py-2 px-4">Rank</th>
                                        <th className="py-2 px-4">District</th>
                                        <th className="py-2 px-4 text-right">Observed</th>
                                        <th className="py-2 px-4 text-right">Frontier</th>
                                        <th className="py-2 px-4 text-right">TE</th>
                                        <th className="py-2 px-4 text-right">Gap</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-50">
                                    {data.district_results.map(d => (
                                        <tr key={d.cdk} className="hover:bg-slate-50 transition-colors">
                                            <td className="py-2 px-4 font-mono text-slate-500">#{d.rank}</td>
                                            <td className="py-2 px-4 font-medium text-slate-800">{d.name}</td>
                                            <td className="py-2 px-4 text-right font-mono">{Math.round(d.observed_yield)}</td>
                                            <td className="py-2 px-4 text-right font-mono text-violet-600">{Math.round(d.frontier_yield)}</td>
                                            <td className="py-2 px-4 text-right font-mono font-bold">
                                                <span className={d.technical_efficiency >= 0.8 ? 'text-emerald-600' : d.technical_efficiency >= 0.6 ? 'text-amber-600' : 'text-rose-600'}>
                                                    {(d.technical_efficiency * 100).toFixed(1)}%
                                                </span>
                                            </td>
                                            <td className="py-2 px-4 text-right font-mono text-slate-500">{d.yield_gap_pct.toFixed(1)}%</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}
        </main>
    );
}
