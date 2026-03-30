'use client';

import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import { Network, TrendingUp, TrendingDown, MapPin, ShieldIcon } from 'lucide-react';
import ReactECharts from 'echarts-for-react';

export default function SpatialContagionPage() {
    const [selectedState, setSelectedState] = useState('');
    const [selectedCdk, setSelectedCdk] = useState('');
    const [selectedCrop, setSelectedCrop] = useState('wheat');
    const [yearRange, setYearRange] = useState('2000-2020');

    const startYear = parseInt(yearRange.split('-')[0]);
    const endYear = parseInt(yearRange.split('-')[1]);

    // Queries
    const { data: summaryData } = useQuery({ queryKey: ['stateSummary'], queryFn: api.getSummary, staleTime: 3600000 });
    const states = useMemo(() => {
        if (!summaryData?.states) return [];
        if (Array.isArray(summaryData.states)) return summaryData.states;
        return Object.keys(summaryData.states).sort();
    }, [summaryData]);

    const {
        data: districtsResponse,
        isLoading: loadingDistricts,
        isError: districtsError,
    } = useQuery({
        queryKey: ['districtsByState', selectedState],
        queryFn: () => api.getDistrictsByState(selectedState),
        enabled: !!selectedState,
    });

    const allDistricts = useMemo(() => {
        if (!districtsResponse?.items) return [];
        return districtsResponse.items
            .map(d => ({ cdk: d.cdk, name: d.name }))
            .sort((a, b) => a.name.localeCompare(b.name));
    }, [districtsResponse]);

    const { data: contagion, isLoading: loadingContagion, isError } = useQuery({
        queryKey: ['spatialContagion', selectedCdk, selectedCrop, startYear, endYear],
        queryFn: () => api.getSpatialContagion(selectedCdk, selectedCrop, startYear, endYear),
        enabled: !!selectedCdk,
    });

    const hasData = !!contagion;

    // Chart Configuration
    const barOption = useMemo(() => {
        if (!contagion) return null;

        // Prepare data for the bar chart
        // Center the 0 axis. We'll show target vs neighbors.
        const targetData = { name: `${contagion.target.name} (Target)`, value: contagion.target.cagr, itemStyle: { color: '#6366f1' } };
        const neighborsData = contagion.neighbors.map(n => ({
            name: n.name,
            value: n.cagr,
            itemStyle: { color: n.cagr > 0 ? '#10b981' : '#f43f5e' }
        }));

        const allData = [targetData, ...neighborsData].sort((a, b) => b.value - a.value);

        return {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: '{b}: {c}% CAGR' },
            grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
            xAxis: {
                type: 'value',
                axisLabel: { formatter: '{value}%' },
                splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } }
            },
            yAxis: {
                type: 'category',
                data: allData.map(d => d.name),
                axisTick: { show: false },
                axisLine: { show: false },
                axisLabel: { color: '#64748b', fontSize: 11 }
            },
            series: [
                {
                    name: 'CAGR (%)',
                    type: 'bar',
                    data: allData,
                    label: {
                        show: true,
                        position: 'insideRight',
                        formatter: '{c}%',
                        color: '#fff',
                        fontSize: 10
                    },
                    markLine: {
                        data: [{ xAxis: contagion.regional_avg_cagr, name: 'Regional Average' }],
                        lineStyle: { type: 'dashed', color: '#94a3b8', width: 2 },
                        label: { formatter: 'Avg: {c}%', position: 'end', color: '#64748b' }
                    }
                }
            ]
        };
    }, [contagion]);

    return (
        <main className="page-container">

            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center gap-4 mb-8 border-b border-slate-200 pb-6">
                <div className="p-3 bg-violet-100 text-violet-700 rounded-xl shadow-inner mt-1 shrink-0">
                    <Network size={24} />
                </div>
                <div>
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-violet-50 border border-violet-200 text-[10px] font-bold text-violet-700 uppercase tracking-widest mb-2">
                        <MapPin size={10} /> Spatial Topography
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Spatial Contagion Analysis</h1>
                    <p className="text-sm text-slate-500 mt-1 max-w-3xl">
                        Analyzes agricultural growth spillovers using PostGIS `ST_Touches` capabilities. Compares a target district&apos;s yield Compound Annual Growth Rate (CAGR) directly against the aggregate performance of its geographic neighbors.
                    </p>
                </div>
            </div>

            {/* Configuration Panel */}
            <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6 shadow-sm flex flex-col sm:flex-row gap-4 items-end">
                <div className="flex-1">
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">State</label>
                    <select
                        value={selectedState}
                        onChange={(e) => { setSelectedState(e.target.value); setSelectedCdk(''); }}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
                    >
                        <option value="">Select state...</option>
                        {states.map((s: string) => <option key={s} value={s}>{s}</option>)}
                    </select>
                </div>

                <div className="flex-1">
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Target District</label>
                    <select
                        value={selectedCdk}
                        onChange={(e) => setSelectedCdk(e.target.value)}
                        disabled={!selectedState || allDistricts.length === 0}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-violet-500 outline-none disabled:opacity-50"
                    >
                        <option value="">
                            {!selectedState
                                ? 'Select a state first...'
                                : loadingDistricts
                                    ? 'Loading districts...'
                                    : districtsError
                                        ? 'Failed to load districts'
                                        : allDistricts.length === 0
                                            ? 'No districts available'
                                            : 'Select target...'}
                        </option>
                        {allDistricts.map(d => (
                            <option key={d.cdk} value={d.cdk}>{d.name} ({d.cdk})</option>
                        ))}
                    </select>
                    {selectedState && districtsError && (
                        <p className="mt-2 text-xs text-rose-600 font-medium">
                            District options could not be loaded for {selectedState}. Please retry or refresh.
                        </p>
                    )}
                    {selectedState && !loadingDistricts && !districtsError && allDistricts.length === 0 && (
                        <p className="mt-2 text-xs text-slate-500 font-medium">
                            No district list was returned for {selectedState}.
                        </p>
                    )}
                </div>

                <div className="w-40">
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Crop</label>
                    <select
                        value={selectedCrop}
                        onChange={(e) => setSelectedCrop(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-violet-500 outline-none"
                    >
                        {['wheat', 'rice', 'cotton', 'sugarcane', 'maize', 'groundnut'].map(c => (
                            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                        ))}
                    </select>
                </div>

                <div className="w-48">
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Time Period</label>
                    <select
                        value={yearRange}
                        onChange={(e) => setYearRange(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-violet-500 outline-none"
                    >
                        {['2000-2020', '1990-2010', '1980-2000', '1970-1990'].map(y => (
                            <option key={y} value={y}>{y}</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Loading State */}
            {loadingContagion && (
                <div className="flex items-center justify-center py-20 bg-white border border-slate-200 rounded-xl">
                    <div className="w-8 h-8 border-2 border-violet-200 border-t-violet-600 rounded-full animate-spin mr-3" />
                    <span className="text-sm text-slate-500 font-medium">Computing PostGIS adjacency matrices...</span>
                </div>
            )}


            {/* Error State */}
            {isError && (
                <div className="bg-white border border-rose-200 rounded-xl p-10 text-center shadow-sm">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-rose-50 flex items-center justify-center">
                        <Network size={24} className="text-rose-400" />
                    </div>
                    <h3 className="text-lg font-bold text-slate-700">Failed to Load Data</h3>
                    <p className="text-sm text-slate-500 mt-1">The server returned an error. Please try a different selection or refresh the page.</p>
                </div>
            )}

            {/* No Data State */}
            {!loadingContagion && selectedCdk && !hasData && (
                <div className="bg-white border border-slate-200 rounded-xl p-10 text-center shadow-sm">
                    <ShieldIcon size={36} className="mx-auto mb-3 text-slate-300" />
                    <h3 className="text-lg font-bold text-slate-700">No Boundary Match</h3>
                    <p className="text-sm text-slate-500 mt-1">Unable to compute spatial touch-points for this district, or historical crop data is missing.</p>
                </div>
            )}

            {/* Results Dashboard */}
            {hasData && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {/* Summary Cluster */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {/* Spillover Category Card */}
                        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm col-span-1 md:col-span-2 relative overflow-hidden flex flex-col justify-center">
                            <div className="absolute -right-8 -top-8 text-slate-50 opacity-50">
                                <Network size={200} />
                            </div>
                            <div className="relative z-10">
                                <div className="text-[10px] uppercase font-bold text-slate-400 mb-2">Spillover Classification</div>
                                <div className={`text-4xl font-bold mb-2 flex items-center gap-3 ${contagion.spillover_category === 'Outperformer' ? 'text-indigo-600' :
                                    contagion.spillover_category === 'Underperformer' ? 'text-rose-600' :
                                        contagion.spillover_category.includes('Clustered') ? 'text-emerald-600' :
                                            'text-amber-600'
                                    }`}>
                                    {contagion.spillover_category}
                                    {contagion.spillover_category === 'Outperformer' && <TrendingUp size={32} />}
                                    {contagion.spillover_category === 'Underperformer' && <TrendingDown size={32} />}
                                </div>
                                <p className="text-slate-500 text-sm max-w-md">
                                    The target district achieved a <span className="font-bold text-slate-800">{contagion.target.cagr}%</span> yield CAGR, compared to its neighbors varying at an average of <span className="font-bold text-slate-800">{contagion.regional_avg_cagr}%</span>.
                                </p>
                            </div>
                        </div>

                        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm flex flex-col justify-center">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Geographic Connections</div>
                            <div className="text-4xl font-bold font-mono text-slate-900 mb-1">{contagion.neighbors.length}</div>
                            <div className="text-sm text-slate-500">Immediate bordering districts found via ST_Touches</div>
                        </div>
                    </div>

                    {/* Chart Row */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Analysis Chart */}
                        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <h2 className="text-sm font-bold text-slate-900 mb-4">{selectedCrop.charAt(0).toUpperCase() + selectedCrop.slice(1)} Yield Growth (CAGR) Comparison</h2>
                            <div className="h-[350px] w-full">
                                <ReactECharts option={barOption!} style={{ height: '100%', width: '100%' }} />
                            </div>
                        </div>

                        {/* Neighbors Table */}
                        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col h-[420px]">
                            <div className="p-4 border-b border-slate-200 bg-slate-50">
                                <h2 className="text-sm font-bold text-slate-900">Adjacent Neighbors</h2>
                            </div>
                            <div className="flex-1 overflow-y-auto">
                                <table className="w-full text-left text-sm">
                                    <tbody className="divide-y divide-slate-100">
                                        {contagion.neighbors.map((n) => (
                                            <tr key={n.cdk} className="hover:bg-slate-50 transition-colors">
                                                <td className="py-3 px-4 font-medium text-slate-800">{n.name}</td>
                                                <td className="py-3 px-4 text-right">
                                                    <span className={`font-mono font-bold ${n.cagr > 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                                                        {n.cagr > 0 ? '+' : ''}{n.cagr.toFixed(2)}%
                                                    </span>
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
