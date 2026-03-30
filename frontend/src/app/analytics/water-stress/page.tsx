'use client';

import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import { Droplet, AlertTriangle, Info, Table2, Activity } from 'lucide-react';
import ReactECharts from 'echarts-for-react';

interface WaterStressTooltipDatum {
    name: string;
    value: [number, number, number, string, number];
}

export default function WaterStressPage() {
    const [selectedState, setSelectedState] = useState('');
    const [selectedYear, setSelectedYear] = useState(2020);
    const [viewMode, setViewMode] = useState<'chart' | 'table'>('chart');

    // Queries
    const { data: summaryData } = useQuery({ queryKey: ['stateSummary'], queryFn: api.getSummary, staleTime: 3600000 });
    const states = useMemo(() => {
        if (!summaryData?.states) return [];
        if (Array.isArray(summaryData.states)) return summaryData.states;
        return Object.keys(summaryData.states).sort();
    }, [summaryData]);

    const { data: stressData, isLoading: loadingStress, isError } = useQuery({
        queryKey: ['waterStress', selectedState, selectedYear],
        queryFn: () => api.getWaterStress(selectedState, selectedYear),
        enabled: !!selectedState,
    });

    const districts = useMemo(() => stressData?.districts || [], [stressData]);
    const hasData = districts.length > 0;

    // Analytics Summary
    const summary = useMemo(() => {
        if (!hasData) return null;

        const critical = districts.filter(d => d.category === 'Critical').length;
        const high = districts.filter(d => d.category === 'High').length;
        const totalWaterIntensive = districts.reduce((sum, d) => sum + d.water_intensive_area, 0);
        const totalArea = districts.reduce((sum, d) => sum + d.total_area, 0);

        const stateAvgRainfall = districts.reduce((sum, d) => sum + d.annual_rainfall, 0) / districts.length;

        return {
            criticalCount: critical,
            highCount: high,
            overallShare: (totalWaterIntensive / totalArea) * 100,
            avgRainfall: stateAvgRainfall,
            highestStress: districts[0] // Since it's sorted by mismatch_score descending
        };
    }, [districts, hasData]);

    // Scatter Plot Configuration
    const scatterOption = useMemo(() => {
        if (!hasData) return null;

        return {
            title: {
                text: 'Agro-Climatic Mismatch Analysis',
                subtext: 'Water-Intensive Crop Share vs Historical Rainfall Normal',
                left: 'center',
                textStyle: { fontSize: 14, color: '#1e293b' },
                subtextStyle: { color: '#64748b' }
            },
            grid: { left: '8%', right: '8%', bottom: '10%', top: '15%', containLabel: true },
            tooltip: {
                trigger: 'item',
                formatter: function (params: WaterStressTooltipDatum) {
                    return `<div class="font-bold border-b border-slate-200 pb-1 mb-1">${params.name}</div>
                            <div class="text-xs space-y-1">
                                <div><span class="text-slate-500">Mismatch Score:</span> <span class="font-bold font-mono text-slate-800">${params.value[2].toFixed(1)}</span></div>
                                <div><span class="text-slate-500">Category:</span> <span class="font-bold ${params.value[3] === 'Critical' ? 'text-rose-600' : params.value[3] === 'High' ? 'text-amber-600' : 'text-slate-600'}">${params.value[3]}</span></div>
                                <div><span class="text-slate-500">Water Intensive:</span> <span class="font-mono text-slate-800">${params.value[0].toFixed(1)}%</span></div>
                                <div><span class="text-slate-500">Annual Rainfall:</span> <span class="font-mono text-slate-800">${params.value[1].toFixed(0)} mm</span></div>
                            </div>`;
                }
            },
            xAxis: {
                name: 'Water-Intensive Crop Share (%)',
                nameLocation: 'middle',
                nameGap: 30,
                type: 'value',
                max: 100,
                axisLabel: { formatter: '{value}%' },
                splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } }
            },
            yAxis: {
                name: 'Historical Annual Rainfall (mm)',
                nameLocation: 'middle',
                nameGap: 50,
                type: 'value',
                splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } }
            },
            dataZoom: [
                { type: 'inside', xAxisIndex: 0, filterMode: 'filter' },
                { type: 'inside', yAxisIndex: 0, filterMode: 'filter' }
            ],
            visualMap: {
                type: 'piecewise',
                dimension: 2, // Map to mismatch score
                pieces: [
                    { min: 60, label: 'Critical Mismatch', color: '#e11d48' }, // Rose 600
                    { min: 40, max: 60, label: 'High Stress', color: '#d97706' }, // Amber 600
                    { min: 20, max: 40, label: 'Moderate', color: '#fcd34d' }, // Amber 300
                    { max: 20, label: 'Sustainable', color: '#10b981' } // Emerald 500
                ],
                orient: 'horizontal',
                bottom: 0,
                left: 'center',
                textStyle: { color: '#64748b' }
            },
            series: [{
                type: 'scatter',
                symbolSize: function (data: [number, number, number, string, number]) {
                    // Bubble size relative to total agricultural area
                    return Math.max(8, Math.min(30, Math.sqrt(data[4]) / 10));
                },
                itemStyle: {
                    opacity: 0.8,
                    borderColor: '#fff',
                    borderWidth: 1
                },
                data: districts.map(d => ({
                    name: d.district_name,
                    value: [
                        d.water_intensive_share, // x
                        d.annual_rainfall,      // y
                        d.mismatch_score,       // mapped to visual map
                        d.category,             // tooltip
                        d.total_area            // size
                    ]
                })),
                markArea: {
                    silent: true,
                    itemStyle: { color: 'rgba(225, 29, 72, 0.05)' }, // Light rose
                    data: [[
                        { xAxis: 50, yAxis: 0 }, // X > 50%, Y < 1000mm = Danger zone
                        { xAxis: 100, yAxis: 1000 }
                    ]]
                }
            }]
        };
    }, [districts, hasData]);

    return (
        <main className="page-container">

            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center gap-4 mb-8 border-b border-slate-200 pb-6">
                <div className="p-3 bg-sky-100 text-sky-700 rounded-xl shadow-inner mt-1 shrink-0">
                    <Droplet size={24} />
                </div>
                <div>
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-sky-50 border border-sky-200 text-[10px] font-bold text-sky-700 uppercase tracking-widest mb-2">
                        <Activity size={10} /> Climatic Risk
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Water Stress Index</h1>
                    <p className="text-sm text-slate-500 mt-1 max-w-3xl">
                        Identifies unsustainable agricultural practices by matching the cultivation footprint of highly water-intensive crops (Rice, Sugarcane, Cotton) against an area&apos;s 50-year historical rainfall normals.
                    </p>
                </div>
            </div>

            {/* Configuration Panel */}
            <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6 shadow-sm flex flex-col sm:flex-row gap-4 items-end">
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

                <div className="w-48">
                    <label className="text-[10px] uppercase font-bold text-slate-600 mb-1 block">Analysis Year</label>
                    <select
                        value={selectedYear}
                        onChange={(e) => setSelectedYear(Number(e.target.value))}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-sky-500 outline-none"
                    >
                        {[2020, 2015, 2010, 2005, 2000, 1995].map(y => (
                            <option key={y} value={y}>{y}</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Loading State */}
            {loadingStress && (
                <div className="flex items-center justify-center py-20 bg-white border border-slate-200 rounded-xl">
                    <div className="w-8 h-8 border-2 border-sky-200 border-t-sky-600 rounded-full animate-spin mr-3" />
                    <span className="text-sm text-slate-500 font-medium">Computing spatial climatic mismatch...</span>
                </div>
            )}


            {/* Error State */}
            {isError && (
                <div className="bg-white border border-rose-200 rounded-xl p-10 text-center shadow-sm">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-rose-50 flex items-center justify-center">
                        <Droplet size={24} className="text-rose-400" />
                    </div>
                    <h3 className="text-lg font-bold text-slate-700">Failed to Load Data</h3>
                    <p className="text-sm text-slate-500 mt-1">The server returned an error. Please try a different selection or refresh the page.</p>
                </div>
            )}

            {/* No Data State */}
            {!loadingStress && selectedState && !hasData && (
                <div className="bg-white border border-slate-200 rounded-xl p-10 text-center shadow-sm">
                    <Droplet size={36} className="mx-auto mb-3 text-slate-500" />
                    <h3 className="text-lg font-bold text-slate-700">No Data Available</h3>
                    <p className="text-sm text-slate-500 mt-1">Either rainfall normals or crop area records are missing for this state and year.</p>
                </div>
            )}

            {/* Results Dashboard */}
            {hasData && summary && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {/* Summary Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="bg-white border border-rose-200 rounded-xl p-4 shadow-sm relative overflow-hidden">
                            <div className="absolute top-0 right-0 p-3 opacity-10">
                                <AlertTriangle size={64} className="text-rose-600" />
                            </div>
                            <div className="text-[10px] uppercase font-bold text-rose-500 mb-1">Critical Zones</div>
                            <div className="text-3xl font-bold font-mono text-rose-700">{summary.criticalCount}</div>
                            <div className="text-xs text-rose-600/70 mt-1 font-medium">Districts in extreme deficit</div>
                        </div>

                        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-600 mb-1">Statewide Intensive Share</div>
                            <div className="text-2xl font-bold font-mono text-slate-900">{summary.overallShare.toFixed(1)}%</div>
                            <div className="text-xs text-slate-500 mt-1">Of total cultivated area</div>
                        </div>

                        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-600 mb-1">Avg State Rainfall</div>
                            <div className="text-2xl font-bold font-mono text-slate-900">{Math.round(summary.avgRainfall)} <span className="text-sm text-slate-500 font-sans">mm</span></div>
                            <div className="text-xs text-slate-500 mt-1">Historical Annual Normal</div>
                        </div>

                        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-600 mb-1">Highest Stress Area</div>
                            <div className="text-lg font-bold text-slate-900 truncate" title={summary.highestStress.district_name}>
                                {summary.highestStress.district_name}
                            </div>
                            <div className="text-xs text-slate-500 mt-1">
                                Score: <span className="font-mono font-bold text-rose-600">{summary.highestStress.mismatch_score.toFixed(1)}</span>
                            </div>
                        </div>
                    </div>

                    {/* Main Content Area */}
                    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                        {/* View Toggle */}
                        <div className="flex border-b border-slate-200 bg-slate-50/50">
                            <button
                                onClick={() => setViewMode('chart')}
                                className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-semibold transition-colors ${viewMode === 'chart' ? 'bg-white text-sky-700 border-b-2 border-sky-500' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100'}`}
                            >
                                <Activity size={16} /> Scatter Analysis
                            </button>
                            <button
                                onClick={() => setViewMode('table')}
                                className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-semibold transition-colors ${viewMode === 'table' ? 'bg-white text-sky-700 border-b-2 border-sky-500' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100'}`}
                            >
                                <Table2 size={16} /> District Rankings
                            </button>
                        </div>

                        <div className="p-5">
                            {viewMode === 'chart' ? (
                                <div className="h-[500px] w-full relative">
                                    <div className="absolute top-4 right-4 z-10 bg-slate-800/90 text-white text-xs p-2 rounded-lg max-w-[200px] pointer-events-none backdrop-blur-sm shadow-xl">
                                        <p className="font-bold flex items-center gap-1.5 mb-1 text-slate-200"><Info size={12} /> The Danger Zone</p>
                                        <p className="text-slate-500">Bottom-Right indicates high cultivation of thirsty crops in arid geographies.</p>
                                    </div>
                                    <ReactECharts option={scatterOption!} style={{ height: '100%', width: '100%' }} />
                                </div>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left border-collapse text-sm">
                                        <thead>
                                            <tr className="bg-slate-50 border-y border-slate-200 text-slate-500 text-xs uppercase tracking-wider">
                                                <th className="py-3 px-4 font-semibold">Rank</th>
                                                <th className="py-3 px-4 font-semibold">District</th>
                                                <th className="py-3 px-4 font-semibold text-right">Mismatch Score</th>
                                                <th className="py-3 px-4 font-semibold">Category</th>
                                                <th className="py-3 px-4 font-semibold text-right">Intensive Share</th>
                                                <th className="py-3 px-4 font-semibold text-right">Rainfall Normal</th>
                                                <th className="py-3 px-4 font-semibold text-right">Total Cultivated</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-100">
                                            {districts.map((d, i) => (
                                                <tr key={d.cdk} className="hover:bg-slate-50 transition-colors">
                                                    <td className="py-3 px-4 text-slate-600 font-mono">#{i + 1}</td>
                                                    <td className="py-3 px-4 font-medium text-slate-900">{d.district_name}</td>
                                                    <td className="py-3 px-4 text-right font-mono font-bold text-slate-700">{d.mismatch_score.toFixed(1)}</td>
                                                    <td className="py-3 px-4">
                                                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${d.category === 'Critical' ? 'bg-rose-100 text-rose-700' :
                                                            d.category === 'High' ? 'bg-amber-100 text-amber-700' :
                                                                d.category === 'Moderate' ? 'bg-amber-50 text-amber-600 border border-amber-200' :
                                                                    'bg-emerald-50 text-emerald-600 border border-emerald-200'
                                                            }`}>
                                                            {d.category}
                                                        </span>
                                                    </td>
                                                    <td className="py-3 px-4 text-right font-mono text-slate-600">{d.water_intensive_share.toFixed(1)}%</td>
                                                    <td className="py-3 px-4 text-right font-mono text-slate-600">{Math.round(d.annual_rainfall)} mm</td>
                                                    <td className="py-3 px-4 text-right font-mono text-slate-600">{d.total_area.toFixed(0)} ha</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </main>
    )
}
