"use client";

import React from 'react';
import ReactECharts from 'echarts-for-react';

interface ChartDataPoint {
    year: number;
    [key: string]: number;
}

interface ScatterChartProps {
    data: ChartDataPoint[];
    xAxisMetric: string; // e.g., 'area'
    yAxisMetric: string; // e.g., 'production'
    color?: string;
}

interface ScatterTooltipParam {
    value: [number, number, number];
}

export function ScatterChart({ data, xAxisMetric, yAxisMetric, color = '#3B82F6' }: ScatterChartProps) {
    if (!data || data.length === 0) {
        return (
            <div className="flex items-center justify-center h-64 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                <span className="text-slate-500 font-medium">No data available for chart</span>
            </div>
        );
    }

    const scatterData = data.map(d => [d[xAxisMetric], d[yAxisMetric], d.year]);

    return (
        <div className="w-full h-80 bg-white border border-slate-200 rounded-xl p-4 md:p-5 shadow-sm">
            <ReactECharts
                option={{
                    tooltip: {
                        trigger: 'item',
                        formatter: function (params: ScatterTooltipParam) {
                            return `Year: ${params.value[2]}<br/>${xAxisMetric}: ${params.value[0]}<br/>${yAxisMetric}: ${params.value[1]}`;
                        }
                    },
                    grid: { top: 30, right: 15, bottom: 20, left: 55 },
                    xAxis: {
                        type: 'value',
                        name: xAxisMetric.charAt(0).toUpperCase() + xAxisMetric.slice(1),
                        nameLocation: 'middle',
                        nameGap: 30,
                        splitLine: { lineStyle: { type: 'dashed' } }
                    },
                    yAxis: {
                        type: 'value',
                        name: yAxisMetric.charAt(0).toUpperCase() + yAxisMetric.slice(1),
                        splitLine: { lineStyle: { type: 'dashed' } }
                    },
                    series: [
                        {
                            symbolSize: 12,
                            data: scatterData,
                            type: 'scatter',
                            itemStyle: { color, opacity: 0.8 }
                        }
                    ]
                }}
                style={{ height: '100%', width: '100%' }}
            />
        </div>
    );
}
