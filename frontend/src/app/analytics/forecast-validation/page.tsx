'use client';

import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import { ApiError } from '../../services/api/client';
import { AINarrative } from '../../components/AINarrative';
import { CheckCircle2, Activity, XCircle, Info, AlertTriangle, Search } from 'lucide-react';
import ReactECharts from 'echarts-for-react';

const GRADE_BADGES: Record<string, { bg: string; text: string }> = {
    A: { bg: 'bg-emerald-100', text: 'text-emerald-700' },
    B: { bg: 'bg-teal-100', text: 'text-teal-700' },
    C: { bg: 'bg-amber-100', text: 'text-amber-700' },
    D: { bg: 'bg-orange-100', text: 'text-orange-700' },
    F: { bg: 'bg-rose-100', text: 'text-rose-700' },
};

export default function ForecastValidationPage() {
    const [cdk, setCdk] = useState('');
    const [selectedState, setSelectedState] = useState('');
    const [crop, setCrop] = useState('rice');
    const [searchInput, setSearchInput] = useState('');

    const { data: summaryData } = useQuery({
        queryKey: ['stateSummary'],
        queryFn: api.getSummary,
        staleTime: 3600000,
    });
    const states = useMemo(() => {
        if (!summaryData?.states) return [];
        return (Array.isArray(summaryData.states) ? summaryData.states : Object.keys(summaryData.states)).sort();
    }, [summaryData]);

    const { data: districtsData, isLoading: districtsLoading } = useQuery({
        queryKey: ['state-districts-intelligence', selectedState],
        queryFn: () => api.getDistrictsByState(selectedState),
        enabled: !!selectedState,
        staleTime: 3600000,
    });
    const districts = districtsData?.items || [];

    const { data, isLoading, isError, error } = useQuery({
        queryKey: ['forecastValidation', cdk, crop],
        queryFn: () => api.getForecastValidation(cdk, crop),
        enabled: !!cdk,
        staleTime: 300_000,
        retry: 1,
    });

    const apiError = error instanceof ApiError ? error : null;
    const isNoDataError = !!apiError && [400, 404, 422].includes(apiError.status);
    const hasData = !!data && data.steps?.length > 0;
    const grade = data?.trustworthiness_grade || '-';
    const gradeBadge = GRADE_BADGES[grade] || GRADE_BADGES.C;

    const chartOption = hasData ? {
        tooltip: { trigger: 'axis' },
        legend: { data: ['Actual', 'Predicted'], bottom: 0, textStyle: { color: '#64748b' } },
        grid: { left: '5%', right: '5%', bottom: '15%', top: '10%', containLabel: true },
        xAxis: { type: 'category', data: data.steps.map(s => s.forecast_year), axisLabel: { color: '#64748b' } },
        yAxis: { type: 'value', name: 'Yield (kg/ha)', splitLine: { lineStyle: { color: '#f1f5f9' } } },
        series: [
            {
                name: 'Actual', type: 'bar',
                data: data.steps.map(s => ({
                    value: s.actual,
                    itemStyle: { color: s.within_ci ? '#10b981' : '#ef4444', borderRadius: [4, 4, 0, 0] },
                })),
                barMaxWidth: 24,
            },
            {
                name: 'Predicted', type: 'line', smooth: true,
                data: data.steps.map(s => s.predicted),
                lineStyle: { color: '#6366f1', width: 2 },
                itemStyle: { color: '#6366f1' },
                symbol: 'circle', symbolSize: 6,
            },
        ],
    } : null;

    return (
        <main className="page-container">
            <div className="flex flex-col md:flex-row md:items-center gap-4 mb-8 border-b border-slate-200 pb-6">
                <div className="p-3 bg-indigo-100 text-indigo-700 rounded-xl shadow-inner mt-1 shrink-0">
                    <CheckCircle2 size={24} />
                </div>
                <div>
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-indigo-50 border border-indigo-200 text-[10px] font-bold text-indigo-700 uppercase tracking-widest mb-2">
                        <Activity size={10} /> Model Transparency
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Forecast Backtesting Panel</h1>
                    <p className="text-sm text-slate-500 mt-1 max-w-3xl">
                        Walk-forward cross-validation that tests our yield forecasting model on historical data.
                        Quantifies accuracy with RMSE, MAPE, confidence interval coverage, and directional accuracy.
                    </p>
                </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6 shadow-sm">
                <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
                    <div className="md:col-span-3">
                        <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">State</label>
                        <select
                            value={selectedState}
                            onChange={(e) => {
                                setSelectedState(e.target.value);
                                setCdk('');
                                setSearchInput('');
                            }}
                            className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
                        >
                            <option value="">Select state...</option>
                            {states.map((state) => (
                                <option key={state} value={state}>{state}</option>
                            ))}
                        </select>
                    </div>

                    <div className="md:col-span-5">
                        <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">District</label>
                        <select
                            value={cdk}
                            onChange={(e) => {
                                setCdk(e.target.value);
                                setSearchInput(e.target.value);
                            }}
                            disabled={!selectedState || districtsLoading}
                            className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none disabled:opacity-60"
                        >
                            <option value="">
                                {!selectedState
                                    ? 'Select state first...'
                                    : districtsLoading
                                        ? 'Loading districts...'
                                        : 'Select district...'}
                            </option>
                            {districts.map((district) => (
                                <option key={district.cdk} value={district.cdk}>
                                    {district.name} ({district.cdk})
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="md:col-span-2">
                        <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Manual CDK</label>
                        <div className="flex gap-2">
                            <input
                                type="text"
                                value={searchInput}
                                onChange={e => setSearchInput(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && setCdk(searchInput.trim())}
                                placeholder="UP_agra_1981"
                                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none font-mono"
                            />
                            <button onClick={() => setCdk(searchInput.trim())} className="px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors">
                                <Search size={16} />
                            </button>
                        </div>
                    </div>

                    <div className="md:col-span-2">
                    <label className="text-[10px] uppercase font-bold text-slate-400 mb-1 block">Crop</label>
                    <select value={crop} onChange={e => setCrop(e.target.value)} className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none">
                        {['rice', 'wheat', 'cotton', 'sugarcane', 'maize', 'groundnut', 'sorghum', 'chickpea'].map(c => (
                            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                        ))}
                    </select>
                </div>
                </div>
                <p className="text-xs text-slate-500 mt-3">
                    Select State and District from dropdowns for easiest use. Manual CDK entry is optional.
                </p>
            </div>

            {isLoading && (
                <div className="flex items-center justify-center py-20 bg-white border border-slate-200 rounded-xl">
                    <div className="w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mr-3" />
                    <span className="text-sm text-slate-500 font-medium">Running walk-forward backtesting...</span>
                </div>
            )}
            {isError && !isNoDataError && (
                <div className="bg-white border border-rose-200 rounded-xl p-10 text-center shadow-sm">
                    <AlertTriangle size={36} className="mx-auto mb-3 text-rose-400" />
                    <h3 className="text-lg font-bold text-slate-700">Backtesting Failed</h3>
                    <p className="text-sm text-slate-500 mt-1">{(error as Error)?.message || 'Insufficient data for backtesting.'}</p>
                </div>
            )}
            {!isLoading && cdk && !hasData && (!isError || isNoDataError) && (
                <div className="bg-white border border-slate-200 rounded-xl p-10 text-center shadow-sm">
                    <Info size={36} className="mx-auto mb-3 text-slate-300" />
                    <h3 className="text-lg font-bold text-slate-700">No Data</h3>
                    <p className="text-sm text-slate-500 mt-1">{apiError?.message || 'Need ≥12 years of yield data for backtesting.'}</p>
                </div>
            )}

            {/* Initial state — nothing selected */}
            {!isLoading && !cdk && !isError && (
                <div className="bg-white border border-dashed border-slate-300 rounded-xl p-10 text-center shadow-sm">
                    <CheckCircle2 size={48} className="mx-auto mb-4 text-indigo-300" />
                    <h3 className="text-lg font-bold text-slate-700">Select a District to Validate</h3>
                    <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
                        Choose a state and district from the dropdowns above, or enter a CDK code manually to run walk-forward cross-validation on the yield forecasting model.
                    </p>
                </div>
            )}

            {hasData && data && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm col-span-1 flex flex-col items-center justify-center">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-2">Trustworthiness</div>
                            <div className={`text-4xl font-black ${gradeBadge.text}`}>{grade}</div>
                            <div className={`mt-2 px-3 py-0.5 rounded-full text-[10px] font-bold ${gradeBadge.bg} ${gradeBadge.text}`}>
                                {grade === 'A' ? 'Excellent' : grade === 'B' ? 'Good' : grade === 'C' ? 'Fair' : grade === 'D' ? 'Poor' : 'Unreliable'}
                            </div>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">RMSE</div>
                            <div className="text-2xl font-bold font-mono text-slate-700">{data.metrics.rmse.toFixed(1)}</div>
                            <div className="text-xs text-slate-500 mt-1">kg/ha deviation</div>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">MAPE</div>
                            <div className="text-2xl font-bold font-mono text-slate-700">{data.metrics.mape.toFixed(1)}%</div>
                            <div className="text-xs text-slate-500 mt-1">Mean absolute % error</div>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">CI Coverage</div>
                            <div className="text-2xl font-bold font-mono text-indigo-600">{data.metrics.coverage_pct.toFixed(0)}%</div>
                            <div className="text-xs text-slate-500 mt-1">Actuals in confidence band</div>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Direction Accuracy</div>
                            <div className="text-2xl font-bold font-mono text-emerald-600">{data.metrics.directional_accuracy.toFixed(0)}%</div>
                            <div className="text-xs text-slate-500 mt-1">Correct up/down calls</div>
                        </div>
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Bias</div>
                            <div className={`text-2xl font-bold font-mono ${data.metrics.bias > 0 ? 'text-sky-600' : data.metrics.bias < -50 ? 'text-rose-600' : 'text-slate-700'}`}>
                                {data.metrics.bias > 0 ? '+' : ''}{data.metrics.bias.toFixed(1)}
                            </div>
                            <div className="text-xs text-slate-500 mt-1">kg/ha {data.metrics.bias < 0 ? '(over-predicting)' : data.metrics.bias > 0 ? '(under-predicting)' : '(unbiased)'}</div>
                        </div>
                    </div>

                    {chartOption && (
                        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                            <h2 className="text-sm font-bold text-slate-900 mb-4">Predicted vs Actual (Walk-Forward)</h2>
                            <div className="h-[350px]">
                                <ReactECharts option={chartOption} style={{ height: '100%', width: '100%' }} />
                            </div>
                            <div className="flex gap-4 mt-3 justify-center text-xs text-slate-500">
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500" /> Within CI</span>
                                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500" /> Outside CI</span>
                            </div>
                        </div>
                    )}

                    <div className="bg-white border border-indigo-100 rounded-xl p-4 text-sm text-indigo-800 shadow-sm">
                        <strong>Interpretation:</strong> {data.interpretation}
                    </div>

                    <AINarrative narrative={data.ai_narrative} />

                    {data.warnings && data.warnings.length > 0 && (
                        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800 shadow-sm">
                            <strong className="flex items-center gap-1.5 mb-1"><AlertTriangle size={14} /> Data Notes:</strong>
                            <ul className="list-disc list-inside space-y-0.5 text-xs mt-1">
                                {data.warnings.map((w, i) => <li key={i}>{w}</li>)}
                            </ul>
                        </div>
                    )}

                    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                        <div className="p-4 border-b border-slate-200 bg-slate-50">
                            <h2 className="text-sm font-bold text-slate-900">Walk-Forward Steps</h2>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-sm">
                                <thead className="bg-white border-b border-slate-200">
                                    <tr className="text-xs uppercase text-slate-400">
                                        <th className="py-2 px-4">Train End</th>
                                        <th className="py-2 px-4">Forecast Year</th>
                                        <th className="py-2 px-4 text-right">Actual</th>
                                        <th className="py-2 px-4 text-right">Predicted</th>
                                        <th className="py-2 px-4 text-right">Error %</th>
                                        <th className="py-2 px-4 text-center">CI</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-50">
                                    {data.steps.map((s, i) => (
                                        <tr key={i} className="hover:bg-slate-50 transition-colors">
                                            <td className="py-2 px-4 font-mono text-slate-500">{s.train_end_year}</td>
                                            <td className="py-2 px-4 font-mono font-bold">{s.forecast_year}</td>
                                            <td className="py-2 px-4 text-right font-mono">{Math.round(s.actual)}</td>
                                            <td className="py-2 px-4 text-right font-mono text-indigo-600">{Math.round(s.predicted)}</td>
                                            <td className="py-2 px-4 text-right font-mono">
                                                <span className={Math.abs(s.error_pct) > 15 ? 'text-rose-600 font-bold' : 'text-slate-600'}>
                                                    {s.error_pct.toFixed(1)}%
                                                </span>
                                            </td>
                                            <td className="py-2 px-4 text-center">
                                                {s.within_ci
                                                    ? <CheckCircle2 size={16} className="text-emerald-500 mx-auto" />
                                                    : <XCircle size={16} className="text-rose-400 mx-auto" />
                                                }
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
