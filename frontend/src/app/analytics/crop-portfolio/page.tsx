'use client';

import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import { Wheat, TrendingUp, TrendingDown, Minus, BarChart3, Grid3X3 } from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import EmptyState from '../../components/EmptyState';

interface ChartTooltipParam {
    name: string;
    value: number;
}

const PIE_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#6366f1', '#14b8a6', '#e11d48'];
const CORR_POSITIVE = '#10b981';
const CORR_NEGATIVE = '#ef4444';

function getCdiColor(cdi: number) {
    if (cdi > 0.7) return '#10b981';
    if (cdi > 0.4) return '#f59e0b';
    return '#ef4444';
}

function getCdiBg(cdi: number) {
    if (cdi > 0.7) return 'border-emerald-500/30';
    if (cdi > 0.4) return 'border-amber-500/30';
    return 'border-red-500/30';
}

export default function CropPortfolioPage() {
    const [selectedState, setSelectedState] = useState<string>('');
    const [selectedCdk, setSelectedCdk] = useState<string>('');
    const [year, setYear] = useState(2014);
    const [rankCrop, setRankCrop] = useState('wheat');

    // Queries
    const { data: states } = useQuery({
        queryKey: ['states-list'],
        queryFn: () => api.getStatesList(),
    });

    const { data: districtsData } = useQuery({
        queryKey: ['state-districts', selectedState],
        queryFn: () => api.getDistrictsByState(selectedState),
        enabled: !!selectedState,
    });
    const districts = districtsData?.items || [];

    const { data: diversification, isLoading } = useQuery({
        queryKey: ['diversification', selectedCdk, year],
        queryFn: () => api.getDiversification(selectedCdk, year),
        enabled: !!selectedCdk,
    });

    const { data: rankings } = useQuery({
        queryKey: ['rankings', selectedState, rankCrop, year],
        queryFn: () => api.getDistrictRankings(selectedState, rankCrop, year),
        enabled: !!selectedState,
    });

    const { data: yieldTrend } = useQuery({
        queryKey: ['yield-trend', selectedCdk, diversification?.dominant_crop],
        queryFn: () => api.getYieldTrend(selectedCdk, diversification?.dominant_crop || 'rice'),
        enabled: !!selectedCdk && !!diversification?.dominant_crop,
    });

    const { data: yoyGrowth } = useQuery({
        queryKey: ['yoy-growth', selectedCdk, diversification?.dominant_crop],
        queryFn: () => api.getYoyGrowth(selectedCdk, diversification?.dominant_crop || 'rice'),
        enabled: !!selectedCdk && !!diversification?.dominant_crop,
    });

    const { data: correlations } = useQuery({
        queryKey: ['crop-correlations', selectedState, year],
        queryFn: () => api.getCropCorrelations(selectedState, year),
        enabled: !!selectedState,
    });

    // Pie chart data — group small crops as "Others"
    const pieData = useMemo(() => {
        if (!diversification?.breakdown) return [];
        const sorted = Object.entries(diversification.breakdown)
            .filter(([, val]) => (val as number) > 0)
            .map(([name, val]) => ({
                name: name.replace(/_/g, ' '),
                value: Math.round((val as number) * 100),
            }))
            .sort((a, b) => b.value - a.value);

        if (sorted.length <= 6) return sorted;

        const top5 = sorted.slice(0, 5);
        const othersVal = sorted.slice(5).reduce((sum, item) => sum + item.value, 0);
        return [...top5, { name: 'Others', value: othersVal }];
    }, [diversification]);

    // Available crops from breakdown for the crop selector
    const availableCrops = useMemo(() => {
        if (!diversification?.breakdown) return ['wheat', 'rice', 'maize'];
        return Object.keys(diversification.breakdown).filter(c => diversification.breakdown[c] > 0);
    }, [diversification]);

    // Yield trend data for LineChart
    const trendLineData = useMemo<{ year: number; yield: number }[]>(() => {
        if (!yoyGrowth?.data) return [];
        return yoyGrowth.data;
    }, [yoyGrowth]);

    // Correlation heatmap data
    const corrCrops = correlations?.crops || [];
    const corrMatrix = correlations?.correlations || {};

    const selectedDistrictName = districts.find(d => d.cdk === selectedCdk)?.name || '';

    return (
        <main className="page-container">
            {/* Header */}
            <div className="mb-8">
                <div className="flex items-center gap-3 mb-1">
                    <Wheat className="text-emerald-600" size={24} />
                    <h1 className="text-2xl font-bold text-slate-900">Crop Portfolio Analyzer</h1>
                </div>
                <p className="text-slate-600 text-sm">Analyze crop diversification, yield trends, and specialization across districts</p>
            </div>

            {/* Selectors */}
            <div className="flex flex-wrap items-center gap-3 mb-8">
                <select
                    value={selectedState}
                    onChange={(e) => { setSelectedState(e.target.value); setSelectedCdk(''); }}
                    className="bg-white border border-slate-300 text-slate-900 rounded-lg px-4 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition min-w-[180px] shadow-sm"
                >
                    <option value="">Select a state...</option>
                    {states?.map((s) => (
                        <option key={s.state} value={s.state}>{s.state}</option>
                    ))}
                </select>
                <select
                    value={selectedCdk}
                    onChange={(e) => setSelectedCdk(e.target.value)}
                    disabled={!selectedState}
                    className="bg-white border border-slate-300 text-slate-900 rounded-lg px-4 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition min-w-[220px] shadow-sm disabled:opacity-50 disabled:bg-slate-50"
                >
                    <option value="">Select a district...</option>
                    {districts.map((d) => (
                        <option key={d.cdk} value={d.cdk}>{d.name}</option>
                    ))}
                </select>
                <input
                    type="number"
                    value={year}
                    onChange={(e) => setYear(Number(e.target.value))}
                    min={1966}
                    max={2020}
                    className="bg-white border border-slate-300 text-slate-900 rounded-lg px-4 py-2 text-sm w-24 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition shadow-sm"
                />
            </div>

            {/* Empty State */}
            {!selectedCdk && !isLoading && (
                <EmptyState icon={Wheat} title="No District Selected" description="Select a state and district above to analyze its crop portfolio and diversification patterns." />
            )}

            {/* Loading */}
            {isLoading && selectedCdk && (
                <div className="flex items-center justify-center py-24">
                    <div className="w-10 h-10 border-2 border-amber-500/30 border-t-amber-500 rounded-full animate-spin" />
                </div>
            )}

            {diversification && (
                <div className="space-y-6 animate-in">
                    {/* District Label */}
                    {selectedDistrictName && (
                        <div className="flex items-center gap-2 text-slate-500 text-sm">
                            <span className="text-xs uppercase tracking-wider text-slate-600 font-bold">Analyzing</span>
                            <span className="text-slate-900 font-bold">{selectedDistrictName}</span>
                            <span className="text-slate-500">•</span>
                            <span className="font-medium text-slate-700">{year}</span>
                        </div>
                    )}

                    {/* ── KPI Cards ── */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {/* CDI Gauge */}
                        <div className={`stat-card text-center border-l-4 ${getCdiBg(diversification.cdi)}`}>
                            <div className="text-xs text-slate-500 uppercase mb-2 tracking-wider font-semibold">Diversification Index</div>
                            <div className="relative w-28 h-28 mx-auto mb-2">
                                <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
                                    <circle cx="60" cy="60" r="52" fill="none" stroke="#e2e8f0" strokeWidth="10" />
                                    <circle
                                        cx="60" cy="60" r="52" fill="none"
                                        stroke={getCdiColor(diversification.cdi)}
                                        strokeWidth="10"
                                        strokeDasharray={`${diversification.cdi * 327} 327`}
                                        strokeLinecap="round"
                                        className="transition-all duration-1000"
                                    />
                                </svg>
                                <div className="absolute inset-0 flex flex-col items-center justify-center pt-1">
                                    <span className="text-2xl font-bold text-slate-900">{(diversification.cdi * 100).toFixed(0)}%</span>
                                </div>
                            </div>
                            <span className="text-xs px-3 py-1 rounded-full font-medium border" style={{
                                backgroundColor: getCdiColor(diversification.cdi) + '15',
                                color: getCdiColor(diversification.cdi),
                                borderColor: getCdiColor(diversification.cdi) + '40'
                            }}>
                                {diversification.interpretation}
                            </span>
                        </div>

                        {/* Dominant Crop */}
                        <div className="stat-card text-center border-l-4 border-amber-500/50">
                            <div className="text-xs text-slate-500 uppercase mb-2 tracking-wider font-semibold">Dominant Crop</div>
                            <div className="text-2xl font-bold text-amber-600 capitalize mb-1 mt-4">
                                {diversification.dominant_crop?.replace(/_/g, ' ')}
                            </div>
                            <div className="text-sm text-slate-500 font-medium">
                                {(diversification.dominant_share * 100).toFixed(1)}% of total area
                            </div>
                            <div className="w-3/4 mx-auto bg-slate-100 rounded-full h-2 mt-4 border border-slate-200">
                                <div
                                    className="h-2 rounded-full bg-amber-500 transition-all duration-700 shadow-sm"
                                    style={{ width: `${diversification.dominant_share * 100}%` }}
                                />
                            </div>
                        </div>

                        {/* Crops Grown */}
                        <div className="stat-card text-center border-l-4 border-indigo-500/50">
                            <div className="text-xs text-slate-500 uppercase mb-2 tracking-wider font-semibold">Crops Grown</div>
                            <div className="text-5xl font-bold text-indigo-600 mb-1 mt-3">{diversification.crop_count}</div>
                            <div className="text-xs text-slate-500 font-medium mt-2">
                                {diversification.crop_count > 8 ? 'Highly diversified portfolio' :
                                    diversification.crop_count > 4 ? 'Moderate crop variety' : 'Limited crop selection'}
                            </div>
                        </div>
                    </div>

                    {/* ── Pie Chart + Rankings ── */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Pie Chart */}
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <h3 className="section-header">Crop Share Distribution</h3>
                            <div className="h-[320px]">
                                <ReactECharts
                                    option={{
                                        tooltip: {
                                            trigger: 'item',
                                            backgroundColor: '#ffffff',
                                            borderColor: '#e2e8f0',
                                            textStyle: { color: '#0f172a' },
                                            formatter: '{b}: {c}% ({d}%)'
                                        },
                                        legend: {
                                            orient: 'vertical',
                                            right: 10,
                                            top: 'center',
                                            textStyle: { color: '#475569', fontSize: 11 }
                                        },
                                        series: [
                                            {
                                                name: 'Crop Share',
                                                type: 'pie',
                                                radius: ['45%', '70%'],
                                                center: ['40%', '50%'],
                                                avoidLabelOverlap: false,
                                                itemStyle: {
                                                    borderRadius: 4,
                                                    borderColor: '#fff',
                                                    borderWidth: 2
                                                },
                                                label: { show: false },
                                                labelLine: { show: false },
                                                data: pieData,
                                                color: PIE_COLORS
                                            }
                                        ]
                                    }}
                                    style={{ height: '100%', width: '100%' }}
                                />
                            </div>
                        </div>

                        {/* District Rankings with crop selector */}
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-2">
                                    <BarChart3 size={14} className="text-indigo-600" />
                                    <h3 className="section-header mb-0">District Yield Rankings</h3>
                                </div>
                                <select
                                    value={rankCrop}
                                    onChange={(e) => setRankCrop(e.target.value)}
                                    className="bg-white border border-slate-300 text-slate-700 rounded-md px-2 py-1 text-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 shadow-sm transition"
                                >
                                    {availableCrops.map(c => (
                                        <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
                                    ))}
                                </select>
                            </div>
                            {rankings && rankings.length > 0 ? (
                                <div className="h-[300px]">
                                    <ReactECharts
                                        option={{
                                            tooltip: {
                                                trigger: 'axis',
                                                axisPointer: { type: 'shadow' },
                                                backgroundColor: '#ffffff',
                                                borderColor: '#e2e8f0',
                                                textStyle: { color: '#0f172a' },
                                                formatter: (params: ChartTooltipParam[]) => {
                                                    const p = params[0];
                                                    return `<div class="font-bold mb-1">${p.name}</div>
                                                            <div class="text-sm text-slate-600">Yield: <span class="text-indigo-600 font-semibold">${p.value.toLocaleString()}</span> kg/ha</div>`;
                                                }
                                            },
                                            grid: { top: 10, right: 30, bottom: 20, left: 10, containLabel: true },
                                            xAxis: {
                                                type: 'value',
                                                splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } },
                                                axisLabel: { color: '#64748b' }
                                            },
                                            yAxis: {
                                                type: 'category',
                                                data: rankings.slice(0, 10).map((d) => d.district).reverse(),
                                                axisLine: { show: false },
                                                axisTick: { show: false },
                                                axisLabel: { color: '#475569', fontWeight: 500 }
                                            },
                                            series: [{
                                                name: 'Yield',
                                                type: 'bar',
                                                data: rankings.slice(0, 10).map((d, i) => ({
                                                    value: d.value,
                                                    itemStyle: { color: PIE_COLORS[(9 - i) % PIE_COLORS.length] }
                                                })).reverse(),
                                                itemStyle: { borderRadius: [0, 4, 4, 0] },
                                                barWidth: '18px'
                                            }]
                                        }}
                                        style={{ height: '100%', width: '100%' }}
                                    />
                                </div>
                            ) : (
                                <div className="text-center py-10 text-slate-500 text-sm">
                                    No ranking data for {rankCrop.replace(/_/g, ' ')} in {year}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* ── Yield Trend ── */}
                    {trendLineData.length > 0 && (
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm mt-6">
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-2">
                                    <TrendingUp size={14} className="text-emerald-600" />
                                    <h3 className="section-header mb-0">
                                        Yield Trend — {(diversification.dominant_crop || '').replace(/_/g, ' ')}
                                    </h3>
                                </div>
                                {yieldTrend && (
                                    <div className="flex items-center gap-2">
                                        {yieldTrend.trend === 'increasing' ? (
                                            <span className="flex items-center gap-1 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-1 rounded-full font-semibold">
                                                <TrendingUp size={12} /> +{yieldTrend.cagr_percent?.toFixed(1) ?? '?'}% CAGR
                                            </span>
                                        ) : yieldTrend.trend === 'decreasing' ? (
                                            <span className="flex items-center gap-1 text-xs text-red-700 bg-red-50 border border-red-200 px-2 py-1 rounded-full font-semibold">
                                                <TrendingDown size={12} /> {yieldTrend.cagr_percent?.toFixed(1) ?? '?'}% CAGR
                                            </span>
                                        ) : (
                                            <span className="flex items-center gap-1 text-xs text-slate-600 bg-slate-100 border border-slate-200 px-2 py-1 rounded-full font-semibold">
                                                <Minus size={12} /> Stable
                                            </span>
                                        )}
                                    </div>
                                )}
                            </div>
                            <div className="h-[250px]">
                                <ReactECharts
                                    option={{
                                        tooltip: {
                                            trigger: 'axis',
                                            backgroundColor: '#ffffff',
                                            borderColor: '#e2e8f0',
                                            textStyle: { color: '#0f172a' },
                                            formatter: (params: ChartTooltipParam[]) => {
                                                const p = params[0];
                                                return `<div class="font-bold mb-1">${p.name}</div>
                                                        <div class="text-sm text-slate-600">Yield: <span class="text-emerald-600 font-semibold">${p.value.toLocaleString()}</span> kg/ha</div>`;
                                            }
                                        },
                                        grid: { top: 10, right: 30, bottom: 20, left: 40, containLabel: false },
                                        xAxis: {
                                            type: 'category',
                                            data: trendLineData.map(d => d.year),
                                            axisLine: { lineStyle: { color: '#cbd5e1' } },
                                            axisTick: { show: false },
                                            axisLabel: { color: '#64748b' }
                                        },
                                        yAxis: {
                                            type: 'value',
                                            splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } },
                                            axisLabel: { color: '#64748b' }
                                        },
                                        series: [{
                                            name: 'Yield',
                                            type: 'line',
                                            data: trendLineData.map(d => d.yield),
                                            smooth: true,
                                            symbol: 'circle',
                                            symbolSize: 6,
                                            itemStyle: { color: '#10b981' }, // emerald-500
                                            lineStyle: { width: 3 },
                                            areaStyle: {
                                                color: {
                                                    type: 'linear',
                                                    x: 0, y: 0, x2: 0, y2: 1,
                                                    colorStops: [{ offset: 0, color: 'rgba(16, 185, 129, 0.2)' }, { offset: 1, color: 'rgba(16, 185, 129, 0)' }]
                                                }
                                            }
                                        }]
                                    }}
                                    style={{ height: '100%', width: '100%' }}
                                />
                            </div>
                        </div>
                    )}

                    {/* ── Crop Correlation Heatmap ── */}
                    {corrCrops.length > 0 && (
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm mt-6">
                            <div className="flex items-center gap-2 mb-4">
                                <Grid3X3 size={14} className="text-indigo-600" />
                                <h3 className="section-header mb-0">Crop Yield Correlations — {selectedState}</h3>
                            </div>
                            <p className="text-xs text-slate-500 mb-4">
                                Green = positive correlation (crops grow together), Red = negative (substitution pattern)
                            </p>
                            <div className="overflow-x-auto">
                                <table className="text-xs w-auto mx-auto border-separate border-spacing-[2px]">
                                    <thead>
                                        <tr>
                                            <th className="p-2 text-slate-500" />
                                            {corrCrops.map((c: string) => (
                                                <th key={c} className="p-2 text-slate-600 capitalize font-semibold text-center min-w-[70px]">
                                                    {c.replace(/_/g, ' ')}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {corrCrops.map((row: string) => (
                                            <tr key={row}>
                                                <td className="p-2 text-slate-600 capitalize font-semibold text-right pr-3">{row.replace(/_/g, ' ')}</td>
                                                {corrCrops.map((col: string) => {
                                                    const val = corrMatrix[row]?.[col];
                                                    const isIdentity = row === col;
                                                    const bgColor = isIdentity ? '#f1f5f9' : // slate-100
                                                        val === null || val === undefined ? '#f8fafc' : // slate-50
                                                            val > 0 ? CORR_POSITIVE : CORR_NEGATIVE;
                                                    const opacity = isIdentity ? 1 : Math.min(Math.abs(val ?? 0), 1);
                                                    return (
                                                        <td
                                                            key={col}
                                                            className="p-2 text-center font-mono rounded"
                                                            style={{
                                                                backgroundColor: isIdentity ? '#f1f5f9' :
                                                                    (val === null || val === undefined) ? '#f8fafc' :
                                                                        `${bgColor}${Math.round(opacity * 200).toString(16).padStart(2, '0')}`,
                                                                color: isIdentity ? '#94a3b8' :
                                                                    val === null || val === undefined ? '#cbd5e1' :
                                                                        val > 0.3 ? '#065f46' : val < -0.3 ? '#991b1b' : '#334155'
                                                            }}
                                                            title={val !== null && val !== undefined ? `${row} × ${col}: ${val}` : 'Insufficient data'}
                                                        >
                                                            {isIdentity ? '—' : val !== null && val !== undefined ? val.toFixed(2) : '·'}
                                                        </td>
                                                    );
                                                })}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* ── Detailed Crop Breakdown Table ── */}
                    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm mt-6">
                        <div className="px-5 py-4 border-b border-slate-200 bg-slate-50">
                            <h3 className="section-header mb-0">Detailed Crop Breakdown</h3>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="text-xs text-slate-500 uppercase bg-white border-b border-slate-200">
                                    <tr>
                                        <th className="px-5 py-3 text-left font-semibold">#</th>
                                        <th className="px-5 py-3 text-left font-semibold">Crop</th>
                                        <th className="px-5 py-3 text-right font-semibold">Share (%)</th>
                                        <th className="px-5 py-3 text-left font-semibold" style={{ minWidth: 200 }}>Visual</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100 bg-white">
                                    {pieData.map((item, i) => (
                                        <tr key={i} className="hover:bg-slate-50 transition">
                                            <td className="px-5 py-3 text-slate-600 text-xs font-mono">{i + 1}</td>
                                            <td className="px-5 py-3 text-slate-700 font-medium capitalize flex items-center gap-2">
                                                <span className="w-2.5 h-2.5 rounded-full flex-shrink-0 shadow-sm" style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }} />
                                                {item.name}
                                            </td>
                                            <td className="px-5 py-3 text-right text-slate-900 font-mono font-semibold">{item.value}%</td>
                                            <td className="px-5 py-3">
                                                <div className="w-full bg-slate-100 rounded-full h-2 shadow-inner">
                                                    <div
                                                        className="h-2 rounded-full transition-all duration-700"
                                                        style={{ width: `${item.value}%`, backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                                                    />
                                                </div>
                                            </td>
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
