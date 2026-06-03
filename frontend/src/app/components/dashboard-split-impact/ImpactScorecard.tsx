import React from 'react';
import { ArrowUpRight, ArrowDownRight, Minus, Loader2 } from 'lucide-react';
import { useSplitImpactAnalysis } from '../../hooks/useSplitImpact';
import { SplitDistrict } from '../../services/api';

interface ImpactScorecardProps {
    event: SplitDistrict;
    crop: string;
}

export function ImpactScorecard({ event, crop }: ImpactScorecardProps) {
    const childNameByCdk = new Map(
        event.children_cdks
            .map((cdk, index) => [cdk, event.children_names[index] || event.children_districts[index]] as const)
            .filter((entry): entry is readonly [string, string] => Boolean(entry[0] && entry[1]))
    );

    const { data, isLoading } = useSplitImpactAnalysis(
        event.parent_cdk,
        event.children_cdks,
        event.split_year,
        crop
    );

    if (isLoading) {
        return (
            <div className="h-24 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-center gap-2 text-slate-500 shadow-sm">
                <Loader2 className="animate-spin text-emerald-600" size={16} />
                <span className="text-xs font-medium">Calculating Impact...</span>
            </div>
        );
    }

    if (!data) return null;

    const { before, after, impact } = data;

    // Safety check for essential data
    if (!impact || !before || !after) return null;

    const isIdsPositive = impact.assessment === 'positive';
    const isNeutral = impact.assessment === 'neutral';
    
    // Extract plain english counterfactual insight if available in advanced stats
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const advancedStats = ('advanced_stats' in data ? data.advanced_stats : ('advancedStats' in data ? data.advancedStats : null)) as any;
    const counterfactualEnglish = advancedStats?.insights?.counterfactual?.plain_english;

    return (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 shadow-sm">
            <h4 className="text-xs font-bold text-slate-600 uppercase mb-3 flex items-center justify-between">
                <span>Split Impact Assessment</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${isIdsPositive
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : isNeutral
                        ? 'bg-slate-100 text-slate-600 border-slate-200'
                        : 'bg-rose-50 text-rose-700 border-rose-200'
                    }`}>
                    {impact.assessment?.toUpperCase() || 'UNKNOWN'}
                </span>
            </h4>

            <div className="grid grid-cols-3 gap-4">
                {/* Before */}
                <div className="flex flex-col">
                    <span className="text-[10px] text-slate-500 font-medium mb-1">Pre-Split Avg ({before.years?.[0] || '?'}-{before.years?.[before.years.length - 1] || '?'})</span>
                    <div className="flex items-end gap-1">
                        <span className="text-lg font-bold text-slate-800">{before.average?.toFixed(0) || '—'}</span>
                        <span className="text-[10px] text-slate-500 font-medium mb-1">kg/ha</span>
                    </div>
                </div>

                {/* Impact Arrow */}
                <div className="flex flex-col items-center justify-center">
                    <div className={`flex items-center gap-1 font-bold ${isIdsPositive ? 'text-emerald-600' : isNeutral ? 'text-slate-500' : 'text-rose-600'
                        }`}>
                        {isIdsPositive ? <ArrowUpRight size={16} /> : isNeutral ? <Minus size={16} /> : <ArrowDownRight size={16} />}
                        <span>{impact.percent_change > 0 ? '+' : ''}{impact.percent_change}%</span>
                    </div>
                </div>

                {/* After */}
                <div className="flex flex-col items-end">
                    <span className="text-[10px] text-slate-500 font-medium mb-1">Post-Split Avg (5yr)</span>
                    <div className="flex items-end gap-1">
                        <span className="text-lg font-bold text-slate-800">{after.combined_average?.toFixed(0) || '—'}</span>
                        <span className="text-[10px] text-slate-500 font-medium mb-1">kg/ha</span>
                    </div>
                </div>
            </div>

            {/* Child Breakdown */}
            <div className="mt-3 pt-3 border-t border-slate-200">
                <div className="text-[10px] text-slate-500 font-medium mb-2">District Contribution (Post-Split):</div>
                <div className="flex flex-wrap gap-2">
                    {after.by_child && Object.entries(after.by_child).map(([cdk, stats]: [string, { avg: number }]) => (
                        <div key={cdk} className="bg-slate-50 border border-slate-200 rounded px-2 py-1 flex items-center gap-2 shadow-sm">
                            <span className="text-[10px] text-slate-800 font-bold">
                                {childNameByCdk.get(cdk) || cdk}
                            </span>
                            <span className="text-[10px] text-slate-500 font-medium">{Math.round(stats.avg)} kg/ha</span>
                        </div>
                    ))}
                </div>
            </div>
            
            {/* Plain English Context */}
            {counterfactualEnglish && (
                <div className="mt-3 pt-3 border-t border-slate-200">
                    <p className="text-xs text-slate-600 italic">
                        {counterfactualEnglish}
                    </p>
                </div>
            )}
        </div>
    );
}
