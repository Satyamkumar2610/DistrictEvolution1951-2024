"use client";

import React from 'react';
import ReactECharts from 'echarts-for-react';

interface ChartDataPoint {
    year: number;
    [key: string]: number;
}

interface BarChartProps {
    data: ChartDataPoint[];
    metrics: string[]; // e.g., ['yield', 'production', 'area']
    colors?: string[];
}

const DEFAULT_COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444']; // Blue, Green, Amber, Red

export function BarChart({ data, metrics, colors }: BarChartProps) {
    if (!data || data.length === 0) {
        return (
            <div className="flex items-center justify-center h-64 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                <span className="text-slate-500 font-medium">No data available for chart</span>
            </div>
        );
    }

    const chartColors = colors || DEFAULT_COLORS;

    return (
        <div className="w-full h-80 bg-white border border-slate-200 rounded-xl p-4 md:p-5 shadow-sm">
            <ReactECharts
                option={{
                    color: chartColors,
                    tooltip: {
                        trigger: 'axis',
                        axisPointer: { type: 'shadow' }
                    },
                    legend: {
                        data: metrics.map(m => m.charAt(0).toUpperCase() + m.slice(1)),
                        bottom: 0
                    },
                    grid: { top: 30, right: 15, bottom: 30, left: 45 },
                    xAxis: {
                        type: 'category',
                        data: data.map(d => String(d.year)),
                    },
                    yAxis: {
                        type: 'value',
                        axisLabel: { formatter: (val: number) => val >= 1000 ? `${(val / 1000).toFixed(1)}k` : val },
                    },
                    series: metrics.map((metric) => ({
                        name: metric.charAt(0).toUpperCase() + metric.slice(1),
                        type: 'bar',
                        data: data.map(d => d[metric]),
                        itemStyle: { borderRadius: [4, 4, 0, 0] }
                    }))
                }}
                style={{ height: '100%', width: '100%' }}
            />
        </div>
    );
}
