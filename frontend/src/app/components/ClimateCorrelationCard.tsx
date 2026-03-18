"use client";

import React from 'react';
import { CloudRain, Info } from 'lucide-react';
import ReactECharts from 'echarts-for-react';

interface ClimateCorrelationCardProps {
    data: {
        correlations: {
            annual_rainfall: { r: number; interpretation: string; direction: string };
            monsoon_rainfall: { r: number; interpretation: string; direction: string };
        };
        data_points: { district: string; yield: number; annual_rainfall: number; monsoon_rainfall: number }[];
        validity?: { warning: string; baseline_period: string; climate_assumption?: string };
    };
    crop: string;
}

export default function ClimateCorrelationCard({ data, crop }: ClimateCorrelationCardProps) {
    const correlations = data?.correlations?.monsoon_rainfall || {};
    const r = correlations.r || 0;
    const direction = correlations.direction || 'neutral';
    const interpretation = correlations.interpretation || 'No Data';

    // Determine color based on Correlation Strength
    const getColor = (rVal: number) => {
        if (Math.abs(rVal) < 0.2) return "text-slate-500"; // Negligible
        if (rVal > 0) return "text-emerald-600"; // Positive
        return "text-rose-600"; // Negative
    };

    const getBgColor = (rVal: number) => {
        if (Math.abs(rVal) < 0.2) return "bg-slate-50 border-slate-200";
        if (rVal > 0) return "bg-emerald-50 border-emerald-200";
        return "bg-rose-50 border-rose-200";
    };

    return (
        <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4 transition-all duration-300 hover:shadow-md hover:border-sky-200">
            {/* Header */}
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
                <h4 className="text-[10px] text-sky-600 uppercase font-bold flex items-center gap-2 tracking-wider">
                    <CloudRain size={14} className="text-sky-500" /> Climate Impact (Monsoon)
                </h4>
                {Math.abs(r) > 0.3 && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${getBgColor(r)} ${getColor(r)} font-bold uppercase`}>
                        {interpretation}
                    </span>
                )}
            </div>

            {/* Stats Row */}
            <div className="flex items-center gap-4 mb-4 bg-slate-50 border border-slate-200 shadow-sm p-4 rounded-xl">
                {/* Big R Value */}
                <div className="flex flex-col items-center">
                    <div className={`text-2xl font-bold font-mono ${getColor(r)}`}>
                        {Math.abs(r) > 0.05 ? `${r > 0 ? '+' : ''}${r.toFixed(2)}` : 'N/A'}
                    </div>
                    <div className="text-[9px] text-slate-500 uppercase tracking-wide font-bold mt-1">Correlation (r)</div>
                </div>

                {/* Intepretation Text */}
                <div className="flex-1 text-xs text-slate-600 leading-relaxed border-l border-slate-200 pl-4">
                    {Math.abs(r) > 0.05 ? (
                        <>
                            <span className="font-semibold text-slate-900 capitalize">{crop}</span> yields have a
                            <span className={`font-bold ${getColor(r)}`}> {interpretation} {direction} </span>
                            relationship with monsoon rainfall in this state.
                        </>
                    ) : (
                        <span className="text-slate-500 italic">Insufficient data for correlation analysis in this region.</span>
                    )}
                </div>
            </div>

            {/* Scatter Plot */}
            <div className="h-48 w-full bg-white border border-slate-200 shadow-sm rounded-xl p-3 mb-3">
                <ReactECharts
                    option={(() => {
                        const points = (data?.data_points || []).map(p => [p.monsoon_rainfall, p.yield] as [number, number]);

                        // Compute simple linear regression for trend line
                        let regressionLine: [number, number][] = [];
                        let rSquared = 0;
                        if (points.length >= 3) {
                            const n = points.length;
                            const sumX = points.reduce((s, p) => s + p[0], 0);
                            const sumY = points.reduce((s, p) => s + p[1], 0);
                            const sumXY = points.reduce((s, p) => s + p[0] * p[1], 0);
                            const sumX2 = points.reduce((s, p) => s + p[0] * p[0], 0);
                            const meanY = sumY / n;
                            const denom = n * sumX2 - sumX * sumX;
                            if (denom !== 0) {
                                const slope = (n * sumXY - sumX * sumY) / denom;
                                const intercept = (sumY - slope * sumX) / n;
                                const xVals = points.map(p => p[0]);
                                const xMin = Math.min(...xVals);
                                const xMax = Math.max(...xVals);
                                regressionLine = [[xMin, slope * xMin + intercept], [xMax, slope * xMax + intercept]];
                                // R²
                                const ssRes = points.reduce((s, p) => s + (p[1] - (slope * p[0] + intercept)) ** 2, 0);
                                const ssTot = points.reduce((s, p) => s + (p[1] - meanY) ** 2, 0);
                                rSquared = ssTot > 0 ? 1 - ssRes / ssTot : 0;
                            }
                        }

                        return {
                            grid: { top: 18, right: 10, bottom: 20, left: 40 },
                            graphic: regressionLine.length > 0 ? [{
                                type: 'text',
                                right: 8,
                                top: 4,
                                style: {
                                    text: `R² = ${rSquared.toFixed(3)}`,
                                    fontSize: 9,
                                    fontFamily: 'monospace',
                                    fill: '#94a3b8',
                                },
                            }] : [],
                            tooltip: {
                                trigger: 'item',
                                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                                borderColor: '#e2e8f0',
                                textStyle: { color: '#0f172a', fontSize: 11 },
                                padding: [8, 12],
                                formatter: function (params: any /* eslint-disable-line @typescript-eslint/no-explicit-any */) {
                                    if (params.seriesName === 'Trend') return '';
                                    return `<b>Yield:</b> ${params.value[1]} kg/ha<br/><b>Rainfall:</b> ${params.value[0]} mm`;
                                }
                            },
                            xAxis: {
                                type: 'value',
                                name: 'Rainfall (mm)',
                                nameLocation: 'middle',
                                nameGap: 25,
                                axisLabel: { color: '#64748b', fontSize: 9 },
                                splitLine: { lineStyle: { color: '#e2e8f0', type: 'dashed' } },
                                axisLine: { show: false },
                                scale: true,
                            },
                            yAxis: {
                                type: 'value',
                                name: 'Yield (kg/ha)',
                                nameLocation: 'end',
                                axisLabel: { color: '#64748b', fontSize: 9, formatter: (val: number) => val >= 1000 ? `${(val / 1000).toFixed(1)}k` : val },
                                splitLine: { lineStyle: { color: '#e2e8f0', type: 'dashed' } },
                                axisLine: { show: false },
                                scale: true,
                            },
                            series: [
                                {
                                    name: 'Districts',
                                    type: 'scatter',
                                    symbolSize: 6,
                                    itemStyle: { color: '#38bdf8', opacity: 0.6 },
                                    data: points,
                                },
                                ...(regressionLine.length > 0 ? [{
                                    name: 'Trend',
                                    type: 'line',
                                    showSymbol: false,
                                    lineStyle: { color: '#6366f1', width: 1.5, type: 'dashed' as const, opacity: 0.5 },
                                    itemStyle: { color: '#6366f1' },
                                    data: regressionLine,
                                    silent: true,
                                    tooltip: { show: false },
                                }] : []),
                            ],
                        };
                    })()}
                    style={{ height: '100%', width: '100%' }}
                />
            </div>

            {/* Methodology Footnote */}
            <div className="flex items-start gap-1.5 text-[9px] text-slate-500 bg-slate-50 p-2.5 rounded-lg border border-slate-200 shadow-sm">
                <Info size={12} className="shrink-0 mt-0.5 text-slate-400" />
                <p>
                    Statistical correlation based on {data?.data_points?.length || 0} districts.
                    Compares {data.validity?.baseline_period || 'historic'} Rainfall Normals vs Yield.
                    Assumption: Climate is stationary (climate_assumption=&quot;{data.validity?.climate_assumption || 'stationary'}&quot;).
                    Results may vary for irrigated regions.
                </p>
            </div>
        </div>
    );
}
