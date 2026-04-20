'use client';

import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import { ShieldCheck, Activity, Info, AlertTriangle } from 'lucide-react';
import ReactECharts from 'echarts-for-react';

const GRADE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
    A: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
    B: { bg: 'bg-teal-50', text: 'text-teal-700', border: 'border-teal-200' },
    C: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
    D: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
    F: { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200' },
};

export default function ResilienceCompositePage() {
    const [selectedState, setSelectedState] = useState('');
    const [selectedCrop, setSelectedCrop] = useState('rice');

    const { data: summaryData } = useQuery({ queryKey: ['stateSummary'], queryFn: api.getSummary, staleTime: 3600000 });
    const states = useMemo(() => {
        if (!summaryData?.states) return [];
        return (Array.isArray(summaryData.states) ? summaryData.states : Object.keys(summaryData.states)).sort();
    }, [summaryData]);

    const { data, isLoading, isError } = useQuery({
        queryKey: ['resilienceComposite', selectedState, selectedCrop],
        queryFn: () => api.getResilienceComposite(selectedState, selectedCrop),
        enabled: !!selectedState,
    });

    const hasData = !!data && data.district_results?.length > 0;

    const radarOption = useMemo(() => {
        if (!data?.variable_contributions) return null;
        const vars = Object.entries(data.variable_contributions);
        const maxV = Math.max(...vars.map(v => v[1]));
        return {
            tooltip: {},
            radar: {
                indicator: vars.map(([name, val]) => ({
                    name: name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                    max: Math.ceil(maxV * 1.2 * 100) / 100,
                })),
                shape: 'polygon',
                splitArea: { areaStyle: { color: ['rgba(99, 102, 241, 0.03)', 'rgba(99, 102, 241, 0.06)'] } },
                axisName: { color: '#475569', fontSize: 10 },
            },
            series: [{
                type: 'radar',
                data: [{ value: vars.map(v => v[1]), name: 'Contribution', areaStyle: { color: 'rgba(99, 102, 241, 0.2)' }, lineStyle: { color: '#6366f1', width: 2 }, itemStyle: { color: '#6366f1' } }],
            }],
        };
    }, [data]);

    const barOption = useMemo(() => {
        if (!hasData) return null;
        const top20 = data.district_results.slice(0, 20);
        return {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            grid: { left: '3%', right: '5%', bottom: '20%', top: '5%', containLabel: true },
            xAxis: {
                type: 'category',
                data: top20.map(d => d.name),
                axisLabel: { rotate: 45, fontSize: 10, color: '#64748b', interval: 0, overflow: 'truncate', width: 60 },
            },
            yAxis: { type: 'value', name: 'Score (0-1)', max: 1, splitLine: { lineStyle: { color: '#f1f5f9' } } },
            series: [{
                type: 'bar',
                data: top20.map(d => ({
                    value: d.resilience_score,
                    itemStyle: {
                        color: d.grade === 'A' ? '#10b981' : d.grade === 'B' ? '#14b8a6' : d.grade === 'C' ? '#f59e0b' : d.grade === 'D' ? '#f97316' : '#ef4444',
                        borderRadius: [4, 4, 0, 0],
                    },
                })),
                barMaxWidth: 28,
            }],
        };
    }, [data, hasData]);

    return (
        <main className="page-container">
            <div className="flex flex-col md:flex-row md:items-center gap-4 mb-8 border-b border-slate-200 pb-6">
                <div className="p-3 bg-teal-100 text-teal-700 rounded-xl shadow-inner mt-1 shrink-0">
                    <ShieldCheck size={24} />
                </div>
                <div>
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-teal-50 border border-teal-200 text-[10px] font-bold text-teal-700 uppercase tracking-widest mb-2">
                        <Activity size={10} /> PCA Composite
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Resilience Composite Index</h1>
                    <p className="text-sm text-slate-500 mt-1 max-w-3xl">
                        8-variable PCA composite capturing yield volatility, drought retention, crop diversification,
                        soil quality, irrigation efficiency, and recovery speed. Districts graded A through F.
                    </p>
                </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6 shadow-sm flex flex-col sm:flex-row gap-4 items-end">
                <div className="flex-1">
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">State</label>
                    <select value={selectedState} onChange={e => setSelectedState(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-teal-500 outline-none">
                        <option value="">Select state...</option>
                        {states.map(s => <option key={s as string} value={s as string}>{s as string}</option>)}
                    </select>
                </div>
                <div className="w-40">
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Crop</label>
                    <select value={selectedCrop} onChange={e => setSelectedCrop(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-teal-500 outline-none">
                        {['rice', 'wheat', 'cotton', 'sugarcane', 'maize', 'groundnut'].map(c => (
                            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                        ))}
                    </select>
                </div>
            </div>

            {isLoading && (
                <div className="flex items-center justify-center py-20 bg-white border border-slate-200 rounded-xl">
                    <div className="w-8 h-8 border-2 border-teal-200 border-t-teal-600 rounded-full animate-spin mr-3" />
                    <span className="text-sm text-slate-500 font-medium">Computing PCA resilience composite...</span>
                </div>
            )}
            {isError && (
                <div className="bg-white border border-rose-200 rounded-xl p-10 text-center shadow-sm">
                    <AlertTriangle size={36} className="mx-auto mb-3 text-rose-400" />
                    <h3 className="text-lg font-bold text-slate-700">Analysis Failed</h3>
                </div>
            )}
            {!isLoading && selectedState && !hasData && !isError && (
                <div className="bg-white border border-slate-200 rounded-xl p-10 text-center shadow-sm">
                    <Info size={36} className="mx-auto mb-3 text-slate-300" />
                    <h3 className="text-lg font-bold text-slate-700">Insufficient Data</h3>
                </div>
            )}

            {hasData && data && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Districts Analyzed</div>
                            <div className="text-2xl font-bold font-mono text-slate-700">{data.n_districts}</div>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Variance Explained</div>
                            <div className="text-2xl font-bold font-mono text-teal-600">{data.total_variance_explained.toFixed(1)}%</div>
                            <div className="text-xs text-slate-500 mt-1">By {data.n_components} PCA components</div>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Mean Resilience Score</div>
                            <div className="text-2xl font-bold font-mono text-indigo-600">{data.mean_score.toFixed(3)}</div>
                        </div>
                        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-emerald-700/70 mb-1">Most Resilient</div>
                            <div className="text-lg font-bold text-emerald-800 truncate">{data.district_results[0]?.name}</div>
                            <div className="text-xs text-emerald-600 mt-1">
                                Score: {data.district_results[0]?.resilience_score.toFixed(3)} (Grade {data.district_results[0]?.grade})
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {radarOption && (
                            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                                <h2 className="text-sm font-bold text-slate-900 mb-3">Variable Contributions</h2>
                                <div className="h-[300px]">
                                    <ReactECharts option={radarOption} style={{ height: '100%', width: '100%' }} />
                                </div>
                            </div>
                        )}
                        {barOption && (
                            <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                                <h2 className="text-sm font-bold text-slate-900 mb-3">Top 20 Districts by Resilience</h2>
                                <div className="h-[300px]">
                                    <ReactECharts option={barOption} style={{ height: '100%', width: '100%' }} />
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                        <div className="p-4 border-b border-slate-200 bg-slate-50">
                            <h2 className="text-sm font-bold text-slate-900">All Districts</h2>
                        </div>
                        <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
                            <table className="w-full text-left text-sm">
                                <thead className="bg-white sticky top-0 border-b border-slate-200 z-10">
                                    <tr className="text-xs uppercase text-slate-400">
                                        <th className="py-2 px-4">#</th>
                                        <th className="py-2 px-4">District</th>
                                        <th className="py-2 px-4 text-right">Score</th>
                                        <th className="py-2 px-4 text-center">Grade</th>
                                        <th className="py-2 px-4">Interpretation</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-50">
                                    {data.district_results.map(d => {
                                        const gc = GRADE_COLORS[d.grade] || GRADE_COLORS.C;
                                        return (
                                            <tr key={d.cdk} className="hover:bg-slate-50 transition-colors">
                                                <td className="py-2 px-4 font-mono text-slate-500">{d.rank}</td>
                                                <td className="py-2 px-4 font-medium text-slate-800">{d.name}</td>
                                                <td className="py-2 px-4 text-right font-mono font-bold">{d.resilience_score.toFixed(3)}</td>
                                                <td className="py-2 px-4 text-center">
                                                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold ${gc.bg} ${gc.text} ${gc.border} border`}>
                                                        {d.grade}
                                                    </span>
                                                </td>
                                                <td className="py-2 px-4 text-xs text-slate-500 max-w-xs truncate" title={d.interpretation}>{d.interpretation}</td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}
        </main>
    );
}
