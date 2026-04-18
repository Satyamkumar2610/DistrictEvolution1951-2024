'use client';

import React, { Suspense, useState, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery, useQueries } from '@tanstack/react-query';
import { api } from '../services/api';
import ReactECharts from 'echarts-for-react';
import { EfficiencyData, RiskData } from '../../types/analysis';
import { GitCompareArrows, X, BarChart3 } from 'lucide-react';
import EmptyState from '../components/EmptyState';
import Tooltip from '../components/Tooltip';

interface ComparisonData {
    cdk: string;
    district: string;
    state: string;
    year: number;
    crop: string;
    efficiency: EfficiencyData | null;
    risk: RiskData | null;
}

const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444'];

function CompareContent() {
    const searchParams = useSearchParams();
    const initialCdks = useMemo(() => {
        const raw = searchParams.get('districts') || searchParams.get('ids') || '';
        return raw.split(',').filter(Boolean);
    }, [searchParams]);

    // State
    const [selectedState, setSelectedState] = useState('');
    const [selectedCdks, setSelectedCdks] = useState<string[]>(initialCdks);
    const [selectedCrop, setSelectedCrop] = useState('wheat');
    const [selectedYear, setSelectedYear] = useState(2020);

    // Queries
    const { data: summaryData } = useQuery({ queryKey: ['stateSummary'], queryFn: api.getSummary, staleTime: 3600000 });
    // The backend returns states as a Record<string, StateSummaryObj>, so we need to extract the keys.
    const states = useMemo(() => {
        if (!summaryData?.states) return [];
        if (Array.isArray(summaryData.states)) return summaryData.states;
        return Object.keys(summaryData.states).sort();
    }, [summaryData]);

    const { data: districtsList } = useQuery({
        queryKey: ['districtsByState', selectedState],
        queryFn: () => api.getDistrictsByState(selectedState),
        enabled: !!selectedState,
    });

    const districts = districtsList?.items || [];

    // Parallel data fetching for comparison
    const queryResults = useQueries({
        queries: selectedCdks.map(cdk => ({
            queryKey: ['comparison', cdk, selectedCrop, selectedYear],
            queryFn: async (): Promise<ComparisonData> => {
                const [efficiency, risk] = await Promise.allSettled([
                    api.getEfficiency(cdk, selectedCrop, selectedYear),
                    api.getRiskProfile(cdk, selectedCrop),
                ]);
                return {
                    cdk,
                    district: cdk,
                    state: '',
                    year: selectedYear,
                    crop: selectedCrop,
                    efficiency: efficiency.status === 'fulfilled' ? efficiency.value : null,
                    risk: risk.status === 'fulfilled' ? risk.value : null,
                };
            },
            staleTime: 1000 * 60 * 30,
            enabled: selectedCdks.length > 0,
        })),
    });

    const loading = queryResults.some(q => q.isLoading);
    const data = queryResults.map(q => q.data).filter(Boolean) as ComparisonData[];

    // Add / remove districts
    const addDistrict = (cdk: string) => {
        if (!selectedCdks.includes(cdk) && selectedCdks.length < 4) {
            setSelectedCdks(prev => [...prev, cdk]);
        }
    };
    const removeDistrict = (cdk: string) => {
        setSelectedCdks(prev => prev.filter(c => c !== cdk));
    };

    // Radar chart
    const radarOption = useMemo(() => {
        if (data.length === 0) return null;
        const indicators = [
            { name: 'Rel. Efficiency', max: 100 },
            { name: 'Resilience', max: 100 },
            { name: 'Stability', max: 100 },
            { name: 'Historical Perf', max: 100 },
        ];

        return {
            tooltip: {
                trigger: 'item',
                backgroundColor: 'rgba(255,255,255,0.95)',
                borderColor: '#e2e8f0',
                textStyle: { color: '#0f172a', fontSize: 12 },
            },
            legend: { bottom: 0, textStyle: { color: '#64748b', fontSize: 11 } },
            radar: {
                indicator: indicators,
                splitNumber: 4,
                axisName: { color: '#64748b', fontSize: 11 },
                splitLine: { lineStyle: { color: '#e2e8f0' } },
                splitArea: { show: false },
                axisLine: { lineStyle: { color: '#cbd5e1' } },
            },
            series: [{
                type: 'radar',
                data: data.map((d, i) => {
                    const eff = d.efficiency?.relative_efficiency?.efficiency_score ?? 0;
                    const res = d.risk?.resilience_index?.resilience_score ?? 0;
                    const vol = d.risk?.risk_profile?.volatility_score ?? 50;
                    const hist = d.efficiency?.historical_efficiency?.efficiency_ratio ?? 1;
                    return {
                        value: [
                            Math.round(eff * 100),
                            Math.round(res * 100),
                            Math.round(Math.max(0, 100 - vol * 2)),
                            Math.round(Math.min(100, Math.max(0, 50 + (hist - 1) * 200))),
                        ],
                        name: d.cdk,
                        itemStyle: { color: COLORS[i % COLORS.length] },
                        areaStyle: { color: COLORS[i % COLORS.length], opacity: 0.2 },
                    };
                }),
            }],
        };
    }, [data]);

    return (
        <main className="page-container">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center gap-4 mb-8 border-b border-slate-200 pb-6">
                <div className="p-3 bg-indigo-100 text-indigo-700 rounded-xl shadow-inner shrink-0">
                    <GitCompareArrows size={24} />
                </div>
                <div>
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-indigo-50 border border-indigo-200 text-[10px] font-bold text-indigo-700 uppercase tracking-widest mb-2">
                        <BarChart3 size={10} /> Multi-District
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Comparative Analysis</h1>
                    <p className="text-sm text-slate-500 mt-1 max-w-2xl">
                        Compare relative efficiency, resilience, volatility, and growth performance across up to 4 districts side-by-side.
                    </p>
                </div>
            </div>

            {/* Configuration — District Selector */}
            <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6 shadow-sm space-y-4">
                <div className="flex flex-col sm:flex-row gap-4 items-end">
                    <div className="flex-1">
                        <label className="text-[10px] uppercase font-bold text-slate-600 mb-1 block">State</label>
                        <select
                            value={selectedState}
                            onChange={(e) => setSelectedState(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
                        >
                            <option value="">Select state...</option>
                            {states.map((s) => <option key={s as string} value={s as string}>{s as string}</option>)}
                        </select>
                    </div>
                    <div className="flex-1">
                        <label className="text-[10px] uppercase font-bold text-slate-600 mb-1 block">Add District</label>
                        <select
                            value=""
                            onChange={(e) => { if (e.target.value) addDistrict(e.target.value); }}
                            disabled={!selectedState || districts.length === 0 || selectedCdks.length >= 4}
                            className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none disabled:opacity-50"
                        >
                            <option value="">{selectedCdks.length >= 4 ? 'Max 4 districts' : 'Add district...'}</option>
                            {districts
                                .filter(d => !selectedCdks.includes(d.cdk))
                                .map(d => <option key={d.cdk} value={d.cdk}>{d.name} ({d.cdk})</option>)}
                        </select>
                    </div>
                    <div className="w-40">
                        <label className="text-[10px] uppercase font-bold text-slate-600 mb-1 block">Crop</label>
                        <select
                            value={selectedCrop}
                            onChange={(e) => setSelectedCrop(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
                        >
                            {['wheat', 'rice', 'maize', 'cotton', 'sugarcane', 'groundnut', 'soyabean'].map(c => (
                                <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                            ))}
                        </select>
                    </div>
                    <div className="w-32">
                        <label className="text-[10px] uppercase font-bold text-slate-600 mb-1 block">Year</label>
                        <select
                            value={selectedYear}
                            onChange={(e) => setSelectedYear(Number(e.target.value))}
                            className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
                        >
                            {[2020, 2019, 2018, 2017, 2016, 2015, 2010, 2005, 2000].map(y => (
                                <option key={y} value={y}>{y}</option>
                            ))}
                        </select>
                    </div>
                </div>

                {/* Selected District Tags */}
                {selectedCdks.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                        {selectedCdks.map((cdk, i) => (
                            <span
                                key={cdk}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border"
                                style={{
                                    backgroundColor: COLORS[i % COLORS.length] + '10',
                                    borderColor: COLORS[i % COLORS.length] + '40',
                                    color: COLORS[i % COLORS.length],
                                }}
                            >
                                {cdk}
                                <button onClick={() => removeDistrict(cdk)} className="hover:opacity-70">
                                    <X size={14} />
                                </button>
                            </span>
                        ))}
                    </div>
                )}
            </div>

            {/* Empty State */}
            {selectedCdks.length === 0 && (
                <EmptyState
                    icon={GitCompareArrows}
                    title="No Districts Selected"
                    description="Select a state and add districts above to begin comparison. You can compare up to 4 districts simultaneously."
                />
            )}

            {/* Loading */}
            {selectedCdks.length > 0 && loading && (
                <div className="flex items-center justify-center py-20 bg-white border border-slate-200 rounded-xl">
                    <div className="w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mr-3" />
                    <span className="text-sm text-slate-500 font-medium">Fetching comparison data...</span>
                </div>
            )}

            {/* Results */}
            {data.length > 0 && !loading && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Radar Chart */}
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm flex flex-col items-center">
                            <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-4 self-start">Strategic Balance</h3>
                            <div className="h-[320px] w-full">
                                {radarOption && <ReactECharts option={radarOption} style={{ height: '100%', width: '100%' }} />}
                            </div>
                        </div>

                        {/* District Cards */}
                        <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-4">
                            {data.map((item, idx) => (
                                <div
                                    key={item.cdk}
                                    className="bg-white border border-slate-200 shadow-sm rounded-xl p-5 relative overflow-hidden"
                                    style={{ borderColor: COLORS[idx % COLORS.length] + '40' }}
                                >
                                    <div className="absolute top-0 left-0 w-full h-1" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />

                                    <div className="flex justify-between items-start mb-4">
                                        <div>
                                            <h2 className="text-lg font-bold text-slate-900">{item.cdk}</h2>
                                            <div className="text-xs text-slate-500">{item.year} • <span className="capitalize">{item.crop}</span></div>
                                        </div>
                                        <div className="text-2xl font-bold" style={{ color: COLORS[idx % COLORS.length] }}>
                                            {String.fromCharCode(65 + idx)}
                                        </div>
                                    </div>

                                    {item.efficiency && item.risk ? (
                                        <div className="space-y-4">
                                            <div className="grid grid-cols-2 gap-3">
                                                <div className="bg-slate-50 border border-slate-100 p-2.5 rounded-lg">
                                                    <div className="text-[10px] text-slate-500 uppercase font-bold tracking-widest flex items-center">
                                                        Rel. Efficiency (vs State)
                                                        <Tooltip text="District yield as % of top 5% state yield. (0-100%, higher = closer to state potential)" />
                                                    </div>
                                                    <div className="text-lg font-bold text-emerald-600">
                                                        {(item.efficiency.relative_efficiency.efficiency_score * 100).toFixed(0)}%
                                                    </div>
                                                    <div className="text-[10px] text-slate-500 font-medium">Gap: {item.efficiency.relative_efficiency.yield_gap_pct.toFixed(1)}%</div>
                                                </div>
                                                <div className="bg-slate-50 border border-slate-100 p-2.5 rounded-lg">
                                                    <div className="text-[10px] text-slate-500 uppercase font-bold tracking-widest flex items-center">
                                                        Resilience
                                                        <Tooltip text="Index combining Yield Stability with historical Drought Retention." />
                                                    </div>
                                                    <div className="text-lg font-bold text-blue-600">
                                                        {(item.risk.resilience_index.resilience_score * 100).toFixed(0)}
                                                    </div>
                                                    <div className="text-[10px] text-slate-500 font-medium">Grade {item.risk.resilience_index.reliability_rating}</div>
                                                </div>
                                            </div>
                                            <div className="border-t border-slate-100 pt-3 space-y-1">
                                                <div className="flex justify-between text-sm">
                                                    <span className="text-slate-500 font-medium flex items-center">
                                                        Hist. Efficiency (vs 10y)
                                                        <Tooltip text="Current yield / 10-year mean yield. 100% = at historical average. Above 100% = above trend." position="right" />
                                                    </span>
                                                    <span className={`font-bold ${item.efficiency.historical_efficiency.is_above_trend ? 'text-blue-600' : 'text-amber-600'}`}>
                                                        {(item.efficiency.historical_efficiency.efficiency_ratio * 100).toFixed(0)}%
                                                    </span>
                                                </div>
                                                <div className="flex justify-between text-sm">
                                                    <span className="text-slate-500 font-medium flex items-center">
                                                        Volatility (CV)
                                                        <Tooltip text="Coefficient of Variation. Higher percentage means more erratic yields." position="right" />
                                                    </span>
                                                    <span className="text-slate-900 font-bold">{item.risk.risk_profile.volatility_score.toFixed(1)}%</span>
                                                </div>
                                                <div className="flex justify-between text-sm">
                                                    <span className="text-slate-500 font-medium">5y CAGR</span>
                                                    <span className={`font-bold ${item.risk.growth_matrix.cagr_5y > 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                                                        {item.risk.growth_matrix.cagr_5y > 0 ? '+' : ''}{item.risk.growth_matrix.cagr_5y}%
                                                    </span>
                                                </div>
                                                <div className="flex justify-between text-sm">
                                                    <span className="text-slate-500 font-medium">Yield (kg/ha)</span>
                                                    <span className="text-slate-900 font-bold">{item.efficiency.relative_efficiency.district_yield.toFixed(0)}</span>
                                                </div>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="text-center text-slate-400 py-8 text-sm">
                                            No data available for this crop/year
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Comparison Table */}
                    <div className="bg-white border border-slate-200 shadow-sm rounded-xl overflow-hidden">
                        <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/50">
                            <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Direct Comparison</h3>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm text-left">
                                <thead className="text-xs text-slate-500 font-bold uppercase bg-slate-50 border-b border-slate-200">
                                    <tr>
                                        <th className="px-6 py-3">Metric</th>
                                        {data.map((d, i) => (
                                            <th key={i} className="px-6 py-3" style={{ color: COLORS[i % COLORS.length] }}>
                                                {d.cdk}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100 text-slate-900">
                                    <tr className="hover:bg-slate-50/50 transition-colors">
                                        <td className="px-6 py-3 font-semibold text-slate-600">
                                            Resilience Index
                                            <Tooltip text="Composite of Yield Stability and Drought Retention (0-100)" position="right" />
                                        </td>
                                        {data.map((d, i) => (
                                            <td key={i} className="px-6 py-3 font-bold font-mono">
                                                {d.risk ? (d.risk.resilience_index.resilience_score * 100).toFixed(0) : '—'}
                                            </td>
                                        ))}
                                    </tr>
                                    <tr className="hover:bg-slate-50/50 transition-colors">
                                        <td className="px-6 py-3 font-semibold text-slate-600">
                                            Relative Efficiency (vs State)
                                            <Tooltip text="District yield / State top-5% yield. 100% = at state potential." position="right" />
                                        </td>
                                        {data.map((d, i) => (
                                            <td key={i} className="px-6 py-3 font-mono">
                                                {d.efficiency ? (d.efficiency.relative_efficiency.efficiency_score * 100).toFixed(1) + '%' : '—'}
                                            </td>
                                        ))}
                                    </tr>
                                    <tr className="hover:bg-slate-50/50 transition-colors">
                                        <td className="px-6 py-3 font-semibold text-slate-600">
                                            Historical Efficiency (vs 10y mean)
                                            <Tooltip text="Current yield / 10-year district mean. 100% = at historical average." position="right" />
                                        </td>
                                        {data.map((d, i) => (
                                            <td key={i} className={`px-6 py-3 font-mono ${d.efficiency?.historical_efficiency?.is_above_trend ? 'text-blue-600' : 'text-amber-600'}`}>
                                                {d.efficiency ? (d.efficiency.historical_efficiency.efficiency_ratio * 100).toFixed(1) + '%' : '—'}
                                            </td>
                                        ))}
                                    </tr>
                                    <tr className="hover:bg-slate-50/50 transition-colors">
                                        <td className="px-6 py-3 font-semibold text-slate-600">Yield (kg/ha)</td>
                                        {data.map((d, i) => (
                                            <td key={i} className="px-6 py-3 font-mono">
                                                {d.efficiency ? d.efficiency.relative_efficiency.district_yield.toFixed(0) : '—'}
                                            </td>
                                        ))}
                                    </tr>
                                    <tr className="hover:bg-slate-50/50 transition-colors">
                                        <td className="px-6 py-3 font-semibold text-slate-600">
                                            Volatility (CV)
                                            <Tooltip text="Standard Deviation / Mean yield. Measures unpredictability." position="right" />
                                        </td>
                                        {data.map((d, i) => (
                                            <td key={i} className="px-6 py-3 font-mono">
                                                {d.risk ? d.risk.risk_profile.volatility_score.toFixed(1) + '%' : '—'}
                                            </td>
                                        ))}
                                    </tr>
                                    <tr className="hover:bg-slate-50/50 transition-colors">
                                        <td className="px-6 py-3 font-semibold text-slate-600">5y CAGR</td>
                                        {data.map((d, i) => (
                                            <td key={i} className={`px-6 py-3 font-bold font-mono ${d.risk && d.risk.growth_matrix.cagr_5y > 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                                                {d.risk ? `${d.risk.growth_matrix.cagr_5y > 0 ? '+' : ''}${d.risk.growth_matrix.cagr_5y}%` : '—'}
                                            </td>
                                        ))}
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}
        </main>
    );
}

export default function ComparePage() {
    return (
        <Suspense fallback={<div className="text-slate-500 font-bold text-center pt-20">Loading comparisons...</div>}>
            <CompareContent />
        </Suspense>
    );
}
