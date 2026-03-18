"use client";
import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, PredictionV2Data } from '../services/api';
import ReactECharts from 'echarts-for-react';
import {
    TrendingUp, TrendingDown,
    ChevronDown, ChevronUp,
    Info, CheckCircle2, AlertCircle
} from 'lucide-react';

interface SimulationPanelProps {
    district: string;
    state: string;
    crop: string;
    year: number;
}

export default function SimulationPanel({ district, state, crop, year }: SimulationPanelProps) {
    const [deviation, setDeviation] = useState<number>(0);
    const [showExplanation, setShowExplanation] = useState(false);

    const { data: predictionData, isLoading, error: queryError } = useQuery({
        queryKey: ['prediction-v2', district, state, crop, year],
        queryFn: () => api.runPredictionV2(district, state, crop, year),
        staleTime: 1000 * 60 * 60,
    });

    const prediction: PredictionV2Data | null = predictionData?.prediction ?? null;
    const error = queryError ? (queryError as Error).message : null;

    const projection = useMemo(() => {
        if (!prediction) return null;
        const rainChangeMM = prediction.mean_rain * (deviation / 100);
        const projectedYield = prediction.predicted_yield + (prediction.slope_rain * rainChangeMM);
        const pctChange = prediction.predicted_yield > 0
            ? ((projectedYield - prediction.predicted_yield) / prediction.predicted_yield) * 100
            : 0;
        return {
            rain_mm: prediction.mean_rain + rainChangeMM,
            yield: Math.max(0, projectedYield),
            change_pct: pctChange,
        };
    }, [prediction, deviation]);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center gap-2 py-6">
                <div className="animate-spin w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full" />
                <span className="text-[10px] text-slate-400 uppercase tracking-widest">Building model...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center gap-2 text-rose-600 text-[11px] py-2">
                <AlertCircle size={13} />
                <span>{error}</span>
            </div>
        );
    }

    if (!prediction || !projection) return null;

    const methodLabel = prediction.method === 'multi_factor_ridge' ? 'Ridge' : 'OLS';

    return (
        <div className="space-y-3">

            {/* ── Model Quality Badges ── */}
            <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                    {methodLabel}
                </span>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                    R² {prediction.r_squared.toFixed(2)}
                </span>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                    {prediction.sample_size} dist
                </span>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                    {prediction.feature_count} feat
                </span>
            </div>

            {/* ── Predicted Yield ── */}
            <div className="bg-white rounded-lg p-3 border border-slate-200 shadow-sm">
                <div className="flex justify-between items-baseline mb-2">
                    <span className="text-[9px] text-slate-500 uppercase tracking-widest font-bold">Predicted Yield</span>
                    <div className={`flex items-center gap-1 text-[11px] font-bold font-mono ${projection.change_pct > 0 ? 'text-emerald-600' : projection.change_pct < 0 ? 'text-rose-600' : 'text-slate-500'
                        }`}>
                        {projection.change_pct > 0 ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                        {projection.change_pct > 0 ? '+' : ''}{projection.change_pct.toFixed(1)}%
                    </div>
                </div>

                <div className="flex items-end justify-between mb-2">
                    <div>
                        <span className={`text-2xl font-bold font-mono tracking-tight ${projection.yield >= prediction.baseline_yield ? 'text-emerald-700' : 'text-amber-600'
                            }`}>
                            {projection.yield.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </span>
                        <span className="text-[10px] text-slate-500 ml-1 font-medium">kg/ha</span>
                    </div>
                    <span className="text-[10px] text-slate-500 font-mono font-medium">
                        base: {prediction.baseline_yield.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </span>
                </div>

                {/* Confidence bar */}
                <div className="relative">
                    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden border border-slate-200/50 shadow-inner">
                        <div className="h-full bg-indigo-500/40 rounded-full" style={{
                            width: '80%',
                            marginLeft: '10%',
                        }} />
                        {(() => {
                            const range = prediction.confidence_upper - prediction.confidence_lower;
                            const pos = range > 0
                                ? ((projection.yield - prediction.confidence_lower) / range) * 100
                                : 50;
                            return (
                                <div
                                    className="absolute top-0 h-1.5 w-1.5 bg-indigo-400 rounded-full -translate-x-1/2 shadow-sm shadow-indigo-400/50"
                                    style={{ left: `${Math.max(3, Math.min(97, pos))}%` }}
                                />
                            );
                        })()}
                    </div>
                    <div className="flex justify-between text-[8px] text-slate-500 mt-0.5 font-mono">
                        <span>{prediction.confidence_lower.toFixed(0)}</span>
                        <span className="text-slate-400 text-[7px] uppercase tracking-widest font-bold">95% CI</span>
                        <span>{prediction.confidence_upper.toFixed(0)}</span>
                    </div>
                </div>
            </div>

            {/* ── Rainfall Deviation Slider ── */}
            <div className="bg-white rounded-lg p-3 border border-slate-200 shadow-sm">
                <div className="flex justify-between items-center mb-2">
                    <span className="text-[9px] text-slate-500 uppercase tracking-widest font-bold">Rainfall Deviation</span>
                    <span className="font-mono text-xs font-bold text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-200">
                        {deviation > 0 ? '+' : ''}{deviation}%
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[8px] font-bold text-rose-500">-50</span>
                    <input
                        type="range"
                        min="-50"
                        max="50"
                        step="5"
                        value={deviation}
                        onChange={(e) => setDeviation(parseInt(e.target.value))}
                        className="flex-1 h-1.5 bg-slate-200 rounded-full appearance-none cursor-pointer accent-indigo-600"
                    />
                    <span className="text-[8px] font-bold text-emerald-600">+50</span>
                </div>
                <div className="text-[9px] text-slate-500 text-center mt-1.5 font-mono font-medium">
                    {projection.rain_mm.toFixed(0)} mm (avg {prediction.mean_rain.toFixed(0)} mm)
                </div>
            </div>

            {/* ── Scatter Plot ── */}
            <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
                <div className="px-3 pt-2">
                    <span className="text-[9px] text-slate-500 uppercase tracking-widest font-bold">Rainfall vs Yield</span>
                </div>
                <div className="h-[180px]">
                    <ReactECharts
                        option={{
                            grid: { top: 15, right: 10, bottom: 22, left: 38 },
                            tooltip: {
                                trigger: 'item',
                                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                                borderColor: '#e2e8f0',
                                textStyle: { color: '#0f172a', fontSize: 10 },
                                padding: [6, 10],
                                formatter: function (params: any /* eslint-disable-line @typescript-eslint/no-explicit-any */) {
                                    if (!params.value || !Array.isArray(params.value) || params.value.length < 2) return '';
                                    if (params.seriesName === 'Projection') {
                                        return `<span style="color:#e11d48;font-weight:600">Projected</span><br/>Yield: ${Number(params.value[1]).toFixed(0)} kg/ha<br/>Rain: ${Number(params.value[0]).toFixed(0)} mm`;
                                    }
                                    if (params.seriesName === 'Trend') return '';
                                    const label = params.data?.[2] || '';
                                    return `${label ? `<span style="color:#64748b;font-weight:600">${label}</span><br/>` : ''}Yield: ${params.value[1]} kg/ha<br/>Rain: ${params.value[0]} mm`;
                                }
                            },
                            xAxis: {
                                type: 'value',
                                name: 'Rain (mm)',
                                nameLocation: 'middle',
                                nameGap: 14,
                                nameTextStyle: { color: '#64748b', fontSize: 8 },
                                axisLabel: { color: '#64748b', fontSize: 8 },
                                splitLine: { lineStyle: { color: '#e2e8f0', type: 'dashed' } },
                                axisLine: { lineStyle: { color: '#cbd5e1' } },
                                axisTick: { show: false },
                                scale: true,
                            },
                            yAxis: {
                                type: 'value',
                                name: 'Yield',
                                nameTextStyle: { color: '#64748b', fontSize: 8 },
                                axisLabel: {
                                    color: '#64748b', fontSize: 8,
                                    formatter: (val: number) => val >= 1000 ? `${(val / 1000).toFixed(1)}k` : String(val),
                                },
                                splitLine: { lineStyle: { color: '#e2e8f0', type: 'dashed' } },
                                axisLine: { lineStyle: { color: '#cbd5e1' } },
                                axisTick: { show: false },
                                scale: true,
                            },
                            series: [
                                // Confidence band — lower bound (invisible baseline)
                                {
                                    name: 'CI Lower',
                                    type: 'line',
                                    showSymbol: false,
                                    lineStyle: { opacity: 0 },
                                    itemStyle: { opacity: 0 },
                                    data: (prediction.regression_line || []).map((p) => [p.x, Math.max(0, p.y - prediction.rmse * 1.96)]),
                                    stack: 'confidence',
                                    silent: true,
                                    tooltip: { show: false },
                                },
                                // Confidence band — upper extent (shaded area stacked on lower)
                                {
                                    name: '95% CI',
                                    type: 'line',
                                    showSymbol: false,
                                    lineStyle: { opacity: 0 },
                                    itemStyle: { opacity: 0 },
                                    areaStyle: { color: '#6366f1', opacity: 0.08 },
                                    data: (prediction.regression_line || []).map((p) => {
                                        const lower = Math.max(0, p.y - prediction.rmse * 1.96);
                                        const upper = p.y + prediction.rmse * 1.96;
                                        return [p.x, upper - lower];
                                    }),
                                    stack: 'confidence',
                                    silent: true,
                                    tooltip: { show: false },
                                },
                                {
                                    name: 'Districts',
                                    type: 'scatter',
                                    symbolSize: 5,
                                    itemStyle: { color: '#818cf8', opacity: 0.6 },
                                    data: (prediction.data_points || []).map((p) => [p.rain, p.yield, p.district]),
                                },
                                {
                                    name: 'Trend',
                                    type: 'line',
                                    showSymbol: false,
                                    lineStyle: { color: '#6366f1', width: 1.5, type: 'dashed', opacity: 0.4 },
                                    itemStyle: { color: '#6366f1' },
                                    data: (prediction.regression_line || []).map((p) => [p.x, p.y]),
                                    silent: true,
                                },
                                {
                                    name: 'Projection',
                                    type: 'scatter',
                                    symbolSize: 8,
                                    symbol: 'diamond',
                                    itemStyle: { color: '#f43f5e', shadowBlur: 4, shadowColor: 'rgba(244,63,94,0.4)' },
                                    data: [[projection.rain_mm, projection.yield]],
                                    markLine: {
                                        data: [{ xAxis: projection.rain_mm }],
                                        lineStyle: { type: 'dashed', color: '#f43f5e', width: 1, opacity: 0.4 },
                                        symbol: ['none', 'none'],
                                        label: { show: false },
                                    },
                                },
                            ],
                        }}
                        style={{ height: '100%', width: '100%' }}
                    />
                </div>
            </div>

            {/* ── Factor Importance ── */}
            {prediction.factors.length > 1 && (
                <div className="bg-white rounded-lg p-3 border border-slate-200 shadow-sm">
                    <span className="text-[9px] text-slate-500 uppercase tracking-widest font-bold">Factor Importance</span>
                    <div className="mt-2 space-y-1.5">
                        {prediction.factors.map((f) => (
                            <div key={f.key}>
                                <div className="flex justify-between items-center mb-0.5">
                                    <span className="text-[10px] text-slate-700 font-medium">{f.name}</span>
                                    <span className="text-[9px] font-mono font-semibold text-slate-500">
                                        {(f.importance * 100).toFixed(0)}%
                                    </span>
                                </div>
                                <div className="h-1 bg-slate-100 rounded-full overflow-hidden shadow-inner border border-slate-200/50">
                                    <div
                                        className={`h-full rounded-full transition-all duration-500 ${f.direction === 'positive'
                                            ? 'bg-indigo-500'
                                            : 'bg-amber-400'
                                            }`}
                                        style={{ width: `${Math.max(3, f.importance * 100)}%` }}
                                    />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* ── Factor Contributions ── */}
            <div className="bg-slate-800/50 rounded-lg border border-slate-700/50 overflow-hidden">
                <div className="px-3 py-2 border-b border-slate-700/50">
                    <span className="text-[9px] text-slate-500 uppercase tracking-widest font-bold">Contributions</span>
                </div>
                {prediction.factors.map((f) => (
                    <div key={f.key} className="px-3 py-1.5 flex items-center justify-between border-b border-slate-800/50 last:border-0">
                        <div className="flex items-center gap-1.5">
                            <div className={`w-1 h-1 rounded-full flex-shrink-0 ${f.direction === 'positive' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                            <span className="text-[10px] text-slate-400">{f.name}</span>
                        </div>
                        <span className={`text-[10px] font-mono font-semibold ${f.contribution >= 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                            {f.contribution >= 0 ? '+' : ''}{f.contribution.toFixed(0)}
                        </span>
                    </div>
                ))}
                <div className="px-3 py-1.5 flex items-center justify-between bg-indigo-500/5 border-t border-indigo-500/10">
                    <span className="text-[10px] text-indigo-300 font-medium">Intercept</span>
                    <span className="text-[10px] font-mono font-semibold text-indigo-300">
                        {(prediction.predicted_yield - prediction.factors.reduce((s, f) => s + f.contribution, 0)).toFixed(0)}
                    </span>
                </div>
            </div>

            {/* ── How This Model Works (Collapsible) ── */}
            <button
                onClick={() => setShowExplanation(!showExplanation)}
                className="w-full flex items-center justify-between px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-left hover:bg-slate-700/30 transition-colors"
            >
                <div className="flex items-center gap-1.5">
                    <Info size={11} className="text-indigo-400" />
                    <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">How This Model Works</span>
                </div>
                {showExplanation ? <ChevronUp size={12} className="text-slate-500" /> : <ChevronDown size={12} className="text-slate-500" />}
            </button>

            {showExplanation && (
                <div className="bg-slate-800/50 rounded-lg border border-slate-700/50 p-3 space-y-3 animate-in fade-in duration-200">
                    {/* Methodology */}
                    <div>
                        <div className="text-[8px] text-slate-500 uppercase tracking-widest font-bold mb-1">Methodology</div>
                        <p className="text-[10px] text-slate-400 leading-relaxed">
                            {prediction.methodology.replace(/\*\*/g, '')}
                        </p>
                    </div>

                    {/* Model Equation */}
                    <div>
                        <div className="text-[8px] text-slate-500 uppercase tracking-widest font-bold mb-1">Equation</div>
                        <div className="bg-slate-900/60 border border-slate-700/50 rounded px-2 py-1.5 font-mono text-[9px] text-indigo-300 overflow-x-auto whitespace-nowrap">
                            {prediction.model_equation}
                        </div>
                    </div>

                    {/* Feature Descriptions */}
                    <div>
                        <div className="text-[8px] text-slate-500 uppercase tracking-widest font-bold mb-1.5">Features</div>
                        <div className="space-y-1">
                            {prediction.factors.map((f) => (
                                <div key={f.key} className="flex items-start gap-1.5">
                                    <CheckCircle2 size={9} className="text-indigo-400 mt-0.5 flex-shrink-0" />
                                    <div className="text-[9px] text-slate-500 leading-snug">
                                        <span className="text-slate-300 font-medium">{f.name}</span>: {f.description}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Data Quality Notes */}
                    {prediction.data_quality_notes.length > 0 && (
                        <div>
                            <div className="text-[8px] text-amber-500/80 uppercase tracking-widest font-bold mb-1">Notes</div>
                            {prediction.data_quality_notes.map((note, i) => (
                                <div key={i} className="flex items-start gap-1.5 mb-0.5">
                                    <AlertCircle size={9} className="text-amber-500/60 mt-0.5 flex-shrink-0" />
                                    <span className="text-[9px] text-slate-500 leading-snug">{note}</span>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Stats row */}
                    <div className="flex flex-wrap gap-x-3 gap-y-1 pt-1 border-t border-slate-700/50">
                        {[
                            { l: 'R²', v: prediction.r_squared.toFixed(3) },
                            { l: 'Adj R²', v: prediction.adjusted_r_squared.toFixed(3) },
                            { l: 'RMSE', v: prediction.rmse.toFixed(0) },
                            { l: 'N', v: String(prediction.sample_size) },
                        ].map((s) => (
                            <div key={s.l} className="text-[8px]">
                                <span className="text-slate-600 uppercase">{s.l} </span>
                                <span className="text-slate-400 font-mono">{s.v}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
