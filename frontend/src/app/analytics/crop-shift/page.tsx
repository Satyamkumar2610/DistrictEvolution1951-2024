'use client';

import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import { Layers, AlertCircle, Info, Sparkles } from 'lucide-react';
import ReactECharts from 'echarts-for-react';

import type { CropShiftTimelinePoint, SplitDistrict } from '../../services/api';

const STATE_COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ec4899', '#06b6d4', '#8b5cf6', '#ef4444', '#14b8a6', '#f97316', '#64748b'];

interface CropShiftTooltipParam {
    name: string | number;
    value: number;
    color: string;
    seriesName: string;
}

// Assign stable colors to specific crops so they look consistent across charts
const getCropColor = (crop: string, index: number) => {
    const cropColors: Record<string, string> = {
        wheat: '#f59e0b',     // Amber
        rice: '#3b82f6',      // Blue
        maize: '#eab308',     // Yellow
        cotton: '#f43f5e',    // Rose
        sugarcane: '#10b981', // Emerald
        soyabean: '#8b5cf6',  // Violet
        groundnut: '#d946ef', // Fuchsia
        sorghum: '#fb923c',   // Orange
        pearl_millet: '#fdba74',
        other: '#cbd5e1'      // Slate
    };
    return cropColors[crop] || STATE_COLORS[index % STATE_COLORS.length];
};

export default function CropShiftPage() {
    const [selectedState, setSelectedState] = useState('');
    const [selectedCdk, setSelectedCdk] = useState('');

    // Queries
    const { data: summaryData } = useQuery({ queryKey: ['stateSummary'], queryFn: api.getSummary, staleTime: 3600000 });
    const states = useMemo(() => {
        if (!summaryData?.states) return [];
        if (Array.isArray(summaryData.states)) return summaryData.states;
        return Object.keys(summaryData.states).sort();
    }, [summaryData]);

    const { data: districtsData } = useQuery({
        queryKey: ['districts', selectedState],
        queryFn: () => api.getSplitEvents(selectedState),
        enabled: !!selectedState,
    });

    // We can extract all unique dists from Split Events (parents + children)
    const allDistricts = useMemo(() => {
        if (!districtsData) return [];
        const distMap = new Map<string, string>();
        districtsData.forEach((event: SplitDistrict) => {
            if (event.parent_cdk && !distMap.has(event.parent_cdk)) {
                distMap.set(event.parent_cdk, event.parent_district);
            }
            event.children_cdks.forEach((cId, i) => {
                if (!cId) return;
                const cName = event.children_districts[i] || event.children_names[i] || cId;
                if (!distMap.has(cId)) distMap.set(cId, cName);
            });
        });
        return Array.from(distMap.entries()).map(([cdk, name]) => ({ cdk, name })).sort((a, b) => a.name.localeCompare(b.name));
    }, [districtsData]);

    const { data: cropShift, isLoading: loadingShift, isError } = useQuery({
        queryKey: ['cropShift', selectedCdk],
        queryFn: () => api.getCropShift(selectedCdk),
        enabled: !!selectedCdk,
    });

    const timeline = cropShift?.timeline;
    const hasData = timeline && timeline.length > 0;

    // Chart Configuration for the Stacked Area Plot
    const chartOption = useMemo(() => {
        if (!hasData) return null;

        const years = timeline.map((point) => point.year);

        // Find all unique crops that appear in any year's top 5
        const allUniqueCrops = new Set<string>();
        timeline.forEach((point: CropShiftTimelinePoint) => {
            Object.keys(point.crop_mix).forEach((crop) => allUniqueCrops.add(crop));
        });
        allUniqueCrops.delete('other'); // handle separately so it's always on top
        const cropList = Array.from(allUniqueCrops);
        cropList.push('other');

        const series = cropList.map((crop, idx) => ({
            name: crop.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()),
            type: 'line',
            stack: 'Total',
            areaStyle: {
                opacity: 0.8,
            },
            emphasis: {
                focus: 'series'
            },
            showSymbol: false,
            // Extract the share (%) for this crop for every year.
            data: timeline.map((point) => parseFloat(((point.crop_mix[crop] || 0) * 100).toFixed(1))),
            color: getCropColor(crop, idx)
        }));

        return {
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross', label: { backgroundColor: '#6a7985' } },
                formatter: function (params: CropShiftTooltipParam[]) {
                    let html = `<div class="font-bold text-slate-800 mb-1">${params[0].name} Crop Mix</div>`;
                    // Sort tooltip by largest share first
                    const sortedParams = [...params].sort((left, right) => right.value - left.value);
                    sortedParams.forEach((point) => {
                        if (point.value > 0) {
                            html += `<div class="flex items-center justify-between gap-4 text-xs mt-1">
                                        <div class="flex items-center gap-1.5">
                                            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background-color:${point.color}"></span>
                                            <span class="text-slate-600">${point.seriesName}</span>
                                        </div>
                                        <span class="font-bold font-mono text-slate-900">${point.value.toFixed(1)}%</span>
                                    </div>`;
                        }
                    });
                    return html;
                }
            },
            legend: {
                data: cropList.map(c => c.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())),
                top: 0,
                icon: 'circle',
                textStyle: { fontSize: 11, color: '#64748b' }
            },
            grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
            xAxis: [
                {
                    type: 'category',
                    boundaryGap: false,
                    data: years,
                    axisLine: { lineStyle: { color: '#cbd5e1' } },
                    axisLabel: { color: '#64748b' }
                }
            ],
            yAxis: [
                {
                    type: 'value',
                    name: 'Area Share (%)',
                    max: 100,
                    axisLine: { lineStyle: { color: '#cbd5e1' } },
                    splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
                    axisLabel: { color: '#64748b' }
                }
            ],
            series: series
        };
    }, [timeline, hasData]);

    // Trend Analysis
    const analytics = useMemo(() => {
        if (!hasData) return null;

        const first = timeline[0];
        const last = timeline[timeline.length - 1];

        const initialDiversity = first.simpson_index;
        const finalDiversity = last.simpson_index;
        const trend = finalDiversity - initialDiversity;

        const initialDominant = first.dominant_crop.replace('_', ' ');
        const finalDominant = last.dominant_crop.replace('_', ' ');

        return {
            firstYear: first.year,
            lastYear: last.year,
            initialDiversity,
            finalDiversity,
            trend: trend > 0.05 ? 'Diversifying' : trend < -0.05 ? 'Concentrating' : 'Stable',
            isShift: initialDominant !== finalDominant,
            initialDominant,
            finalDominant
        };
    }, [timeline, hasData]);


    return (
        <main className="page-container">

            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
                <div className="flex items-start gap-4">
                    <div className="p-3 bg-indigo-100 text-indigo-700 rounded-xl shadow-inner mt-1">
                        <Layers size={24} />
                    </div>
                    <div>
                        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-indigo-50 border border-indigo-200 text-[10px] font-bold text-indigo-700 uppercase tracking-widest mb-2">
                            <Sparkles size={10} /> Advanced Analytics
                        </div>
                        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Crop Diversification Shift</h1>
                        <p className="text-sm text-slate-500">Track longitudinal shifts in agricultural specialization and monoculture risks.</p>
                    </div>
                </div>
            </div>

            {/* Configuration Panel */}
            <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6 shadow-sm flex flex-col sm:flex-row gap-4">
                <div className="flex-1">
                    <label className="text-[10px] uppercase font-bold text-slate-600 mb-1 block">State</label>
                    <select
                        value={selectedState}
                        onChange={(e) => { setSelectedState(e.target.value); setSelectedCdk(''); }}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
                    >
                        <option value="">Select state...</option>
                        {states.map((state) => <option key={state as string} value={state as string}>{state as string}</option>)}
                    </select>
                </div>

                <div className="flex-1">
                    <label className="text-[10px] uppercase font-bold text-slate-600 mb-1 block">District</label>
                    <select
                        value={selectedCdk}
                        onChange={(e) => setSelectedCdk(e.target.value)}
                        disabled={!selectedState || allDistricts.length === 0}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none disabled:opacity-50"
                    >
                        <option value="">Select district...</option>
                        {allDistricts.map(d => (
                            <option key={d.cdk} value={d.cdk}>{d.name} ({d.cdk})</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Loading State */}
            {loadingShift && (
                <div className="flex items-center justify-center py-20 bg-white border border-slate-200 rounded-xl">
                    <div className="w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mr-3" />
                    <span className="text-sm text-slate-500 font-medium">Analyzing multi-decadal crop compositions...</span>
                </div>
            )}


            {/* Error State */}
            {isError && (
                <div className="bg-white border border-rose-200 rounded-xl p-10 text-center shadow-sm">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-rose-50 flex items-center justify-center">
                        <Layers size={24} className="text-rose-400" />
                    </div>
                    <h3 className="text-lg font-bold text-slate-700">Failed to Load Data</h3>
                    <p className="text-sm text-slate-500 mt-1">The server returned an error. Please try a different selection or refresh the page.</p>
                </div>
            )}

            {/* No Data State */}
            {!loadingShift && selectedCdk && !hasData && (
                <div className="bg-white border border-slate-200 rounded-xl p-10 text-center shadow-sm">
                    <AlertCircle size={36} className="mx-auto mb-3 text-slate-500" />
                    <h3 className="text-lg font-bold text-slate-700">No Longitudinal Data</h3>
                    <p className="text-sm text-slate-500 mt-1">There is insufficient historical crop area data to analyze the shift for this district.</p>
                </div>
            )}

            {/* Results Dashboard */}
            {hasData && analytics && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {/* Summary Metrics */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-600 mb-1">Observation Period</div>
                            <div className="text-2xl font-bold font-mono text-slate-900">{analytics.firstYear}–{analytics.lastYear}</div>
                            <div className="text-xs text-slate-500 mt-1">{timeline.length} years of continuous data</div>
                        </div>

                        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-600 mb-1">Diversity Trend</div>
                            <div className={`text-2xl font-bold ${analytics.trend === 'Diversifying' ? 'text-emerald-600' :
                                analytics.trend === 'Concentrating' ? 'text-amber-600' : 'text-slate-900'
                                }`}>
                                {analytics.trend}
                            </div>
                            <div className="text-xs text-slate-500 mt-1">
                                Simpson Index: {analytics.initialDiversity.toFixed(2)} → {analytics.finalDiversity.toFixed(2)}
                            </div>
                        </div>

                        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm col-span-2">
                            <div className="text-[10px] uppercase font-bold text-slate-600 mb-1">Historical Paradigm Shift</div>
                            {analytics.isShift ? (
                                <div>
                                    <div className="text-lg font-bold text-slate-900 flex items-center gap-2">
                                        <span className="capitalize text-slate-500 line-through">{analytics.initialDominant}</span>
                                        <span>→</span>
                                        <span className="capitalize text-indigo-700">{analytics.finalDominant}</span>
                                    </div>
                                    <div className="text-xs text-slate-500 mt-1">
                                        The district fundamentally transitioned its primary agricultural output.
                                    </div>
                                </div>
                            ) : (
                                <div>
                                    <div className="text-lg font-bold text-slate-900 capitalize">{analytics.finalDominant} Dominant</div>
                                    <div className="text-xs text-slate-500 mt-1">
                                        The primary crop remained the same throughout the observed history.
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Chart Area */}
                    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                        <div className="flex items-start justify-between mb-6">
                            <div>
                                <h2 className="text-sm font-bold text-slate-900">Crop Composition Timeline</h2>
                                <p className="text-xs text-slate-500 mt-0.5">Stacked area showing proportional share (100%) of total cropped area.</p>
                            </div>

                            <div className="group relative cursor-help">
                                <Info size={16} className="text-slate-600" />
                                <div className="absolute right-0 top-6 w-64 bg-slate-800 text-white text-xs p-3 rounded-lg shadow-xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20">
                                    <p className="font-bold mb-1">Reading this chart:</p>
                                    <p className="text-slate-500">This normalizes all agricultural area to 100%. Wide bands indicate major crops. If a band widens significantly while others shrink, the district is concentrating towards monoculture.</p>
                                </div>
                            </div>
                        </div>

                        <div className="h-[400px] w-full">
                            <ReactECharts option={chartOption!} style={{ height: '100%', width: '100%' }} />
                        </div>
                    </div>
                </div>
            )}
        </main>
    )
}
