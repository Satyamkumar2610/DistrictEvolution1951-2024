
import React from 'react';
import {
    TrendingUp,
    Activity,
    BarChart3
} from 'lucide-react';
import { AnalysisAdvancedStats } from '../../services/api';



interface AdvancedStatsPanelProps {
    stats: AnalysisAdvancedStats;
    metric: string;
}

export function AdvancedStatsPanel({ stats }: AdvancedStatsPanelProps) {
    if (!stats) return null;

    // unit variable removed as it was unused (stats cards have hardcoded formatting for now)

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4 animate-in fade-in slide-in-from-bottom-2 duration-700">
            {/* Growth Card */}
            <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm relative overflow-hidden group hover:shadow-md transition-shadow">
                <div className="absolute top-0 right-0 p-3 opacity-5 group-hover:opacity-10 transition-opacity">
                    <TrendingUp size={48} className="text-emerald-500" />
                </div>
                <h4 className="flex items-center gap-2 text-emerald-600 font-bold text-sm mb-3">
                    <TrendingUp size={16} /> Growth Dynamics (CAGR)
                </h4>
                <div className="flex items-end gap-2">
                    <span className="text-2xl font-bold text-slate-900 tracking-tight">
                        {stats.post.cagr.toFixed(2)}%
                    </span>
                    <span className={`text-xs mb-1.5 px-1.5 py-0.5 rounded font-bold border ${stats.post.cagr > stats.pre.cagr ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-rose-50 text-rose-700 border-rose-200'}`}>
                        {stats.post.cagr > stats.pre.cagr ? 'Accelerated' : 'Slowed'}
                    </span>
                </div>
                <p className="text-xs text-slate-500 mt-2 font-medium">
                    Compound Annual Growth Rate changed from <strong className="text-slate-700">{stats.pre.cagr.toFixed(2)}%</strong> pre-split.
                </p>
            </div>

            {/* Stability Card */}
            <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm relative overflow-hidden group hover:shadow-md transition-shadow">
                <div className="absolute top-0 right-0 p-3 opacity-5 group-hover:opacity-10 transition-opacity">
                    <Activity size={48} className="text-blue-500" />
                </div>
                <h4 className="flex items-center gap-2 text-blue-600 font-bold text-sm mb-3">
                    <Activity size={16} /> Production Stability (CV)
                </h4>
                <div className="flex items-end gap-2">
                    <span className="text-2xl font-bold text-slate-900 tracking-tight">
                        {stats.post.cv.toFixed(2)}%
                    </span>
                    <span className={`text-xs mb-1.5 px-1.5 py-0.5 rounded font-bold border ${stats.post.cv < stats.pre.cv ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-orange-50 text-orange-700 border-orange-200'}`}>
                        {stats.post.cv < stats.pre.cv ? 'More Stable' : 'More Volatile'}
                    </span>
                </div>
                <p className="text-xs text-slate-500 mt-2 font-medium">
                    Coefficient of Variation (Volatility) was <strong className="text-slate-700">{stats.pre.cv.toFixed(2)}%</strong> before the split.
                </p>
            </div>

            {/* Impact Summary */}
            <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm relative overflow-hidden group hover:shadow-md transition-shadow">
                <div className="absolute top-0 right-0 p-3 opacity-5 group-hover:opacity-10 transition-opacity">
                    <BarChart3 size={48} className="text-indigo-500" />
                </div>
                <h4 className="flex items-center gap-2 text-indigo-600 font-bold text-sm mb-3">
                    <BarChart3 size={16} /> Net Performance Impact
                </h4>
                <div className="flex items-end gap-2">
                    <span className="text-2xl font-bold text-slate-900 tracking-tight">
                        {stats.impact.pct_change > 0 ? '+' : ''}{stats.impact.pct_change.toFixed(1)}%
                    </span>
                    <span className="text-xs text-slate-500 mb-1.5 font-medium">avg. shift</span>
                </div>

                {stats.impact.uncertainty && (
                    <div className="mt-2 text-xs">
                        <div className="flex items-center gap-1.5 mb-1">
                            <span className="text-slate-600 font-semibold">
                                (±{((stats.impact.uncertainty.upper - stats.impact.uncertainty.lower) / 2).toFixed(1)}%)
                            </span>
                            {/* Check Significance: If interval crosses 0 (signs differ), it's inconclusive */}
                            {(stats.impact.uncertainty.lower > 0 || stats.impact.uncertainty.upper < 0) ? (
                                <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold uppercase">
                                    Significant
                                </span>
                            ) : (
                                <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200 font-bold uppercase">
                                    Inconclusive
                                </span>
                            )}
                        </div>
                        <div className="text-[9px] text-slate-500 font-medium">
                            95% CI: [{stats.impact.uncertainty.lower.toFixed(1)}, {stats.impact.uncertainty.upper.toFixed(1)}]
                        </div>
                    </div>
                )}

                <p className="text-xs text-slate-500 mt-2 font-medium">
                    Analysis compares average performance levels between the two administrative eras.
                </p>
            </div>
        </div>
    );
}
