import React from 'react';
import { TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle } from 'lucide-react';

export default function EpochMetricsPanel({ 
    epoch, 
    crop 
}: { 
    epoch: any, 
    crop: string 
}) {
    if (!epoch) return null;

    const latestMetric = epoch.metrics && epoch.metrics.length > 0 
        ? epoch.metrics[epoch.metrics.length - 1] 
        : null;

    // Previous epoch metric for comparison (if in metrics array)
    const prevMetric = epoch.metrics && epoch.metrics.length > 1
        ? epoch.metrics[epoch.metrics.length - 2]
        : null;

    const yieldVal = latestMetric?.collective_yield;
    const prodVal = latestMetric?.collective_production;
    const areaVal = latestMetric?.collective_area;
    const coverage = latestMetric?.data_coverage;

    // Calculate year-over-year change
    const yieldChange = yieldVal && prevMetric?.collective_yield
        ? ((yieldVal - prevMetric.collective_yield) / prevMetric.collective_yield) * 100
        : null;

    const metrics = [
        {
            label: "Collective Yield",
            value: yieldVal ? `${yieldVal.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : "N/A",
            unit: "kg/ha",
            change: yieldChange,
            gradient: "from-violet-500/20 to-indigo-500/20",
            border: "border-violet-500/10",
            accent: "text-violet-400",
        },
        {
            label: `${crop} Production`,
            value: prodVal ? `${prodVal.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : "N/A",
            unit: "MT",
            change: null,
            gradient: "from-emerald-500/20 to-teal-500/20",
            border: "border-emerald-500/10",
            accent: "text-emerald-400",
        },
        {
            label: `${crop} Area`,
            value: areaVal ? `${areaVal.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : "N/A",
            unit: "hectares",
            change: null,
            gradient: "from-amber-500/20 to-orange-500/20",
            border: "border-amber-500/10",
            accent: "text-amber-400",
        },
    ];

    return (
        <div className="bg-slate-900/60 backdrop-blur border border-slate-800/50 rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                    Epoch {epoch.epoch_num} Metrics
                    <span className="text-slate-600 ml-2 font-normal normal-case">
                        ({epoch.year_start}–{epoch.year_end || 'present'})
                    </span>
                </h3>
                {coverage !== undefined && (
                    <div className="flex items-center gap-2">
                        <div className="w-20 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                            <div 
                                className={`h-full rounded-full transition-all ${coverage >= 0.8 ? 'bg-emerald-500' : coverage >= 0.5 ? 'bg-amber-500' : 'bg-red-500'}`}
                                style={{ width: `${(coverage * 100)}%` }}
                            />
                        </div>
                        <span className="text-[10px] text-slate-500">{(coverage * 100).toFixed(0)}% coverage</span>
                    </div>
                )}
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {metrics.map((m, i) => (
                    <div key={i} className={`p-4 rounded-xl bg-gradient-to-br ${m.gradient} border ${m.border}`}>
                        <p className={`text-[10px] font-semibold uppercase tracking-wider mb-2 ${m.accent}`}>{m.label}</p>
                        <div className="flex items-baseline gap-2">
                            <p className="text-2xl font-bold text-white">{m.value}</p>
                            <span className="text-xs text-slate-500">{m.unit}</span>
                        </div>
                        {m.change !== null && (
                            <div className={`flex items-center gap-1 mt-2 text-xs ${m.change > 0 ? 'text-emerald-400' : m.change < 0 ? 'text-red-400' : 'text-slate-500'}`}>
                                {m.change > 0 ? <TrendingUp className="w-3 h-3" /> : m.change < 0 ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                                <span>{m.change > 0 ? '+' : ''}{m.change.toFixed(1)}% YoY</span>
                            </div>
                        )}
                    </div>
                ))}
            </div>

            {/* Active districts + flags */}
            <div className="mt-4 flex flex-wrap items-center gap-2">
                <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mr-1">Active:</span>
                {epoch.active_cdks.map((cdk: string, i: number) => (
                    <span key={i} className="px-2 py-1 bg-slate-800/60 text-slate-400 text-[10px] rounded-md border border-slate-700/50 font-mono hover:text-slate-200 hover:border-slate-600 transition cursor-default">
                        {cdk}
                    </span>
                ))}
                
                {epoch.is_fallback && (
                    <span className="ml-2 inline-flex items-center gap-1 px-2 py-1 bg-amber-500/10 text-amber-400 text-[10px] font-medium rounded-md border border-amber-500/20" title={`Using data from: ${(epoch.data_cdks || []).join(', ')}`}>
                        <AlertTriangle className="w-3 h-3" /> Using parent data
                    </span>
                )}
                {epoch.is_virtual && (
                    <span className="ml-2 inline-flex items-center gap-1 px-2 py-1 bg-blue-500/10 text-blue-400 text-[10px] font-medium rounded-md border border-blue-500/20">
                        <AlertTriangle className="w-3 h-3" /> Reconstructed
                    </span>
                )}
                {coverage !== undefined && coverage >= 1.0 && !epoch.is_fallback && (
                    <span className="ml-1 inline-flex items-center gap-1 px-2 py-1 bg-emerald-500/10 text-emerald-400 text-[10px] font-medium rounded-md border border-emerald-500/20">
                        <CheckCircle className="w-3 h-3" /> Full coverage
                    </span>
                )}
            </div>
        </div>
    );
}
