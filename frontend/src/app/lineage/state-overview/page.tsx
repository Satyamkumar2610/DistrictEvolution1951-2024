'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import Link from 'next/link';
import { MapPin, TrendingUp, TrendingDown, Layers, ArrowRight } from 'lucide-react';
import ReactECharts from 'echarts-for-react';

interface BarTooltipParam {
    name: string;
    value: number;
}

const CROPS = [
    { value: 'wheat', label: 'Wheat' },
    { value: 'rice', label: 'Rice' },
    { value: 'maize', label: 'Maize' },
    { value: 'sorghum', label: 'Sorghum' },
    { value: 'cotton', label: 'Cotton' },
    { value: 'soyabean', label: 'Soybean' },
    { value: 'groundnut', label: 'Groundnut' },
    { value: 'sugarcane', label: 'Sugarcane' },
];

export default function StatePage() {
    const [selectedState, setSelectedState] = useState<string>('');
    const [selectedCrop, setSelectedCrop] = useState('wheat');
    const [selectedYear, setSelectedYear] = useState<number | undefined>(undefined);

    const years = Array.from({ length: 2017 - 1966 + 1 }, (_, i) => 2017 - i);

    const { data: states } = useQuery({
        queryKey: ['states-list'],
        queryFn: () => api.getStatesList(),
    });

    const { data: overview, isLoading, isError } = useQuery({
        queryKey: ['state-overview', selectedState, selectedCrop, selectedYear],
        queryFn: () => api.getStateOverview(selectedState, selectedCrop, selectedYear),
        enabled: !!selectedState,
    });

    return (
        <main className="page-container">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-2xl font-bold text-slate-900 mb-1">State Dashboard</h1>
                <p className="text-slate-600 text-sm">Aggregate agricultural analytics by state</p>
            </div>

            {/* Selectors */}
            <div className="flex flex-wrap gap-3 mb-8">
                <select
                    value={selectedState}
                    onChange={(e) => setSelectedState(e.target.value)}
                    className="bg-white border border-slate-300 text-slate-900 rounded-lg px-4 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition min-w-[200px] shadow-sm"
                >
                    <option value="">Select a state...</option>
                    {states?.map((s) => (
                        <option key={s.state} value={s.state}>
                            {s.state} ({s.district_count} districts)
                        </option>
                    ))}
                </select>
                <select
                    value={selectedCrop}
                    onChange={(e) => setSelectedCrop(e.target.value)}
                    className="bg-white border border-slate-300 text-slate-900 rounded-lg px-4 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition shadow-sm"
                >
                    {CROPS.map((c) => (
                        <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                </select>
                <select
                    value={selectedYear ?? ''}
                    onChange={(e) => setSelectedYear(e.target.value ? Number(e.target.value) : undefined)}
                    className="bg-white border border-slate-300 text-slate-900 rounded-lg px-4 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition shadow-sm"
                >
                    <option value="">Latest Year</option>
                    {years.map((y) => (
                        <option key={y} value={y}>{y}</option>
                    ))}
                </select>
            </div>

            {!selectedState && (
                <div className="text-center py-20 bg-white border border-slate-200 rounded-xl shadow-sm">
                    <Layers className="mx-auto text-slate-400 mb-4" size={48} />
                    <h3 className="text-lg font-bold text-slate-700">No State Selected</h3>
                    <p className="text-sm text-slate-500 mt-1">Select a state above to view district counts, boundary changes, and split event statistics.</p>
                </div>
            )}

            {isLoading && selectedState && (
                <div className="flex items-center justify-center py-20">
                    <div className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                </div>
            )}

            {isError && selectedState && !isLoading && (
                <div className="text-center py-20 bg-white border border-rose-200 rounded-xl shadow-sm">
                    <Layers className="mx-auto text-rose-300 mb-4" size={48} />
                    <h3 className="text-lg font-bold text-slate-700">Failed to load state overview</h3>
                    <p className="text-sm text-slate-500 mt-1">The backend did not return overview data for this state and crop selection.</p>
                </div>
            )}

            {overview && !isError && (
                <div className="space-y-8 animate-in">
                    {/* Stats Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="stat-card">
                            <div className="text-xs text-slate-500 uppercase mb-1">Total Districts</div>
                            <div className="stat-value">{overview.total_districts}</div>
                        </div>
                        <div className="stat-card">
                            <div className="text-xs text-slate-500 uppercase mb-1">With Data</div>
                            <div className="stat-value">{overview.districts_with_data}</div>
                            <div className="text-xs text-slate-500 mt-1">for {selectedCrop} in {overview.year}</div>
                        </div>
                        <div className="stat-card">
                            <div className="text-xs text-slate-500 uppercase mb-1">Avg Yield</div>
                            <div className="stat-value">{overview.avg_yield.toLocaleString()}</div>
                            <div className="text-xs text-slate-500 mt-1">kg/ha</div>
                        </div>
                        <div className="stat-card">
                            <div className="text-xs text-slate-500 uppercase mb-1">Data Range</div>
                            <div className="stat-value text-lg">{overview.year_range.min}–{overview.year_range.max}</div>
                        </div>
                    </div>

                    {/* Top & Bottom Performers */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Top 5 */}
                        <div className="glass-card rounded-xl p-5">
                            <div className="flex items-center gap-2 mb-4">
                                <TrendingUp size={16} className="text-emerald-600" />
                                <h3 className="section-header mb-0">Top Performers</h3>
                            </div>
                            <div className="h-[250px]">
                                <ReactECharts
                                    option={{
                                        tooltip: {
                                            trigger: 'axis',
                                            axisPointer: { type: 'shadow' },
                                            backgroundColor: '#ffffff',
                                            borderColor: '#e2e8f0',
                                            textStyle: { color: '#0f172a' },
                                            formatter: (params: BarTooltipParam[]) => {
                                                const p = params[0];
                                                return `<div class="font-bold mb-1">${p.name}</div>
                                                        <div class="text-sm text-slate-600">Yield: <span class="text-emerald-600 font-semibold">${p.value.toLocaleString()}</span> kg/ha</div>`;
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
                                            data: overview.top_performers.map((d) => d.district_name).reverse(),
                                            axisLine: { show: false },
                                            axisTick: { show: false },
                                            axisLabel: { color: '#475569', fontWeight: 500 }
                                        },
                                        series: [{
                                            name: 'Yield',
                                            type: 'bar',
                                            data: overview.top_performers.map((d) => d.yield_value).reverse(),
                                            itemStyle: {
                                                color: '#10b981', // emerald-500
                                                borderRadius: [0, 4, 4, 0]
                                            },
                                            barWidth: '24px'
                                        }]
                                    }}
                                    style={{ height: '100%', width: '100%' }}
                                />
                            </div>
                        </div>

                        {/* Bottom 5 */}
                        <div className="glass-card rounded-xl p-5">
                            <div className="flex items-center gap-2 mb-4">
                                <TrendingDown size={16} className="text-rose-600" />
                                <h3 className="section-header mb-0">Bottom Performers</h3>
                            </div>
                            <div className="h-[250px]">
                                <ReactECharts
                                    option={{
                                        tooltip: {
                                            trigger: 'axis',
                                            axisPointer: { type: 'shadow' },
                                            backgroundColor: '#ffffff',
                                            borderColor: '#e2e8f0',
                                            textStyle: { color: '#0f172a' },
                                            formatter: (params: BarTooltipParam[]) => {
                                                const p = params[0];
                                                return `<div class="font-bold mb-1">${p.name}</div>
                                                        <div class="text-sm text-slate-600">Yield: <span class="text-rose-600 font-semibold">${p.value.toLocaleString()}</span> kg/ha</div>`;
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
                                            data: overview.bottom_performers.map((d) => d.district_name).reverse(),
                                            axisLine: { show: false },
                                            axisTick: { show: false },
                                            axisLabel: { color: '#475569', fontWeight: 500 }
                                        },
                                        series: [{
                                            name: 'Yield',
                                            type: 'bar',
                                            data: overview.bottom_performers.map((d) => d.yield_value).reverse(),
                                            itemStyle: {
                                                color: '#f43f5e', // rose-500
                                                borderRadius: [0, 4, 4, 0]
                                            },
                                            barWidth: '24px'
                                        }]
                                    }}
                                    style={{ height: '100%', width: '100%' }}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Available Crops */}
                    <div className="glass-card rounded-xl p-5">
                        <h3 className="section-header">Available Crops in {overview.state}</h3>
                        <div className="flex flex-wrap gap-2">
                            {overview.available_crops.map((crop) => (
                                <button
                                    key={crop}
                                    onClick={() => setSelectedCrop(crop)}
                                    className={`px-4 py-1.5 rounded-full text-xs font-semibold tracking-wide transition ${crop === selectedCrop
                                        ? 'bg-indigo-50 text-indigo-700 border border-indigo-200 shadow-sm'
                                        : 'bg-slate-50 text-slate-600 border border-slate-200 hover:text-slate-900 hover:border-slate-300 hover:bg-slate-100'
                                        }`}
                                >
                                    {crop.replace(/_/g, ' ')}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Quick Links */}
                    <div className="glass-card rounded-xl p-5">
                        <h3 className="section-header">Explore Districts</h3>
                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                            {overview.top_performers.slice(0, 6).map((d) => (
                                <Link
                                    key={d.cdk}
                                    href={`/explore/map?district=${d.cdk}&crop=${selectedCrop}`}
                                    className="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 transition group"
                                >
                                    <div className="flex items-center gap-2">
                                        <MapPin size={14} className="text-indigo-600" />
                                        <span className="text-sm font-medium text-slate-700">{d.district_name}</span>
                                    </div>
                                    <ArrowRight size={14} className="text-slate-400 group-hover:text-indigo-600 transition" />
                                </Link>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </main>
    );
}
