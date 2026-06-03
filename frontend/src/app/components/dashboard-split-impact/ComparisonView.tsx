
"use client";

import React from 'react';
import { ComparisonChart } from './ComparisonChart';
import { ComparisonTable } from './ComparisonTable';
import { ComparisonContextBanner } from './ComparisonContextBanner';
import { AdvancedStatsPanel } from './AdvancedStatsPanel';
import { MaupReliabilityPanel } from './MaupReliabilityPanel';
import { ImpactScorecard } from './ImpactScorecard';
import { AlertCircle, Sprout, Loader2 } from 'lucide-react';
import { useAnalysis } from '../../hooks/useSplitImpact';
import { AnalysisMode, SplitDistrict } from '../../services/api';

interface ComparisonViewProps {
    event: SplitDistrict;
    crop: string;
    metric: string;
    mode: AnalysisMode;
}

export function ComparisonView({ event, crop, metric, mode }: ComparisonViewProps) {
    const resolvedChildCdks = event.children_cdks.filter((cdk): cdk is string => Boolean(cdk));
    const params = event.parent_cdk && resolvedChildCdks.length > 0 ? {
        parent: event.parent_cdk,
        children: resolvedChildCdks.join(','),
        splitYear: event.split_year,
        crop,
        metric,
        mode
    } : null;

    const { data: payload, isLoading: loading } = useAnalysis(params);

    if (!event) return null;

    const timelineData = payload?.data ?? [];
    const chartSeries = payload?.series ?? [];
    const advancedStats = payload?.advancedStats ?? payload?.advanced_stats;
    const hasData = Boolean(timelineData.length && chartSeries.length);

    return (
        <div className="bg-white p-3 md:p-6 rounded-xl border border-slate-200 shadow-sm animate-in fade-in duration-500 flex flex-col h-full overflow-hidden">
            {/* Context Banner */}
            <ComparisonContextBanner event={event} mode={mode} />

            <div className="flex-1 flex flex-col min-h-0 bg-slate-50 rounded-lg border border-slate-200 overflow-hidden">
                {loading ? (
                    <div className="h-full w-full flex flex-col items-center justify-center text-slate-500 bg-white/50 z-10 gap-3">
                        <Loader2 size={24} className="animate-spin text-indigo-600" />
                        <span className="text-sm font-medium">Analyzing Data...</span>
                    </div>
                ) : !hasData ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-slate-500 p-4 md:p-8 text-center bg-white">
                        <Sprout size={36} className="text-slate-500 mb-3 md:mb-4 md:w-12 md:h-12" />
                        <h3 className="text-base md:text-lg font-bold text-slate-700">No Data Available</h3>
                        <p className="max-w-xs mt-2 text-xs md:text-sm text-slate-500">
                            We found no records for <span className="text-indigo-600 font-bold">{crop.toUpperCase()}</span> in
                            <span className="text-slate-800 font-semibold"> {event.parent_name}</span>.
                        </p>
                        <p className="mt-3 md:mt-4 text-[10px] md:text-xs bg-slate-100 px-3 py-2 rounded-lg text-slate-600 border border-slate-200 font-medium tracking-tight">
                            Try selecting <strong>Rice</strong>, <strong>Maize</strong>, or another crop.
                        </p>
                    </div>
                ) : (
                    <div className="flex-1 overflow-y-auto custom-scrollbar">
                        {/* Impact Scorecard */}
                        <div className="px-3 md:px-4 pt-3 md:pt-4">
                            <ImpactScorecard event={event} crop={crop} />
                        </div>

                        {/* Advanced Stats */}
                        {advancedStats && (
                            <div className="px-3 md:px-4 pt-3 md:pt-4">
                                <AdvancedStatsPanel stats={advancedStats} metric={metric} />
                                <MaupReliabilityPanel maup={advancedStats.insights?.maup} />
                            </div>
                        )}

                        {/* Chart Area */}
                        <div className="min-h-[250px] md:min-h-[300px] p-3 md:p-4">
                            <ComparisonChart
                                data={timelineData}
                                series={chartSeries}
                                splitYear={event.split_year}
                                metric={metric}
                            />
                        </div>

                        {/* Stats Table - Hidden on very small screens */}
                        <div className="px-3 md:px-4 pb-3 md:pb-4 hidden sm:block">
                            <ComparisonTable
                                data={timelineData}
                                series={chartSeries}
                                splitYear={event.split_year}
                            />
                        </div>

                        {/* Footer Note */}
                        <div className="px-3 md:px-4 pb-2 flex items-start gap-2 text-[9px] md:text-[10px] text-slate-500 leading-tight">
                            <AlertCircle size={10} className="mt-0.5 shrink-0 md:w-3 md:h-3" />
                            <p className="line-clamp-2">
                                Data provided by harmonized v1.5 panel.
                                {mode === 'before_after'
                                    ? ' Post-split values are reconstructed aggregates.'
                                    : ' Raw district performance data.'
                                }
                            </p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
