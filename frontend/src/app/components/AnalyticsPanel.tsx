import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';
import { Shield, TrendingUp, AlertTriangle, PieChart, Calculator, Bookmark as BookmarkIcon, Check, ExternalLink } from 'lucide-react';
import SimulationPanel from './SimulationPanel';
import ClimateCorrelationCard from './ClimateCorrelationCard';
import Tooltip from './Tooltip';
import { useBookmarks } from '../hooks/useBookmarks';
import { exportToCSV } from '../../lib/reports';

interface AnalyticsPanelProps {
    cdk: string;
    districtName: string;
    state: string;
    year: number;
    crop: string;
}

export default function AnalyticsPanel({ cdk, districtName, state, year, crop }: AnalyticsPanelProps) {
    const { data: efficiency, isLoading: loadingEff } = useQuery({
        queryKey: ['efficiency', cdk, year, crop],
        queryFn: () => api.getEfficiency(cdk, crop, year),
        enabled: !!cdk
    });

    const { data: riskData, isLoading: loadingRisk } = useQuery({
        queryKey: ['risk', cdk, crop],
        queryFn: () => api.getRiskProfile(cdk, crop),
        enabled: !!cdk
    });

    const { data: diversification, isLoading: loadingDiv } = useQuery({
        queryKey: ['diversification', cdk, year],
        queryFn: () => api.getDiversification(cdk, year),
        enabled: !!cdk
    });

    const { data: correlation, isLoading: loadingCorr } = useQuery({
        queryKey: ['climate-correlation', state, crop, year],
        queryFn: () => api.getClimateCorrelation(state, crop, year),
        enabled: !!state && !!crop
    });

    const { addBookmark, isBookmarked, removeBookmark } = useBookmarks();
    const isSaved = isBookmarked(cdk, year, crop);

    const loading = loadingEff || loadingRisk || loadingDiv || loadingCorr;
    // React Query handles errors internally or we can use isError props

    if (loading) return (
        <div className="p-4 border border-dashed border-slate-300 rounded-lg text-center flex flex-col items-center justify-center min-h-[100px] bg-slate-50/50">
            <div className="animate-spin w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full mb-2"></div>
            <div className="text-slate-500 text-xs font-medium">Loading analytics...</div>
        </div>
    );

    const isError =
        (efficiency === undefined && !loadingEff) ||
        (riskData === undefined && !loadingRisk) ||
        (diversification === undefined && !loadingDiv);

    // Check if we have minimal data to display anything
    const hasData = efficiency || riskData || diversification || correlation;

    if (isError && !hasData) return (
        <div className="p-6 bg-red-50 border border-red-200 rounded-lg text-center min-h-[100px] flex flex-col items-center justify-center shadow-sm">
            <AlertTriangle className="text-red-500 mb-2" size={20} />
            <div className="text-red-700 text-xs font-bold">Analysis Unavailable</div>
            <div className="text-red-600/80 text-[10px] mt-1">Unable to generate insights at this time.</div>
        </div>
    );

    if (!hasData && !loading) return (
        <div className="p-6 bg-slate-50 border border-slate-200 rounded-lg text-center min-h-[100px] flex flex-col items-center justify-center shadow-sm">
            <div className="text-slate-500 text-xs font-medium">No analytics data available for this selection.</div>
        </div>
    );

    const risk = riskData?.risk_profile;

    return (
        <div className="space-y-4 mt-4 animate-in fade-in duration-500 pb-10">

            {/* Header / Actions */}
            <div className="flex justify-between items-center bg-white border border-slate-200 shadow-sm p-2.5 rounded-xl -mt-2 mb-3">
                <span className="text-[10px] text-slate-500 font-mono tracking-wider ml-1 font-semibold">ID: {cdk}</span>

                <div className="flex gap-2">
                    <button
                        onClick={() => {
                            // Construct composite data object for export
                            const exportData = { efficiency: efficiency ?? null, risk: riskData ?? null };
                            // Note: diversification/correlation logic could be added to reports.ts later
                            exportToCSV(exportData, `i-ascap-analysis-${cdk}-${year}.csv`);
                        }}
                        className="flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-bold transition-all border bg-white text-slate-600 border-slate-200 shadow-sm hover:text-blue-600 hover:border-blue-200 hover:bg-blue-50/50"
                    >
                        <ExternalLink size={10} /> Export
                    </button>

                    <button
                        onClick={() => {
                            if (isSaved) {
                                // Find ID to remove? useBookmarks might need logic refactor or just rebuild ID
                                const id = `${cdk}-${year}-${crop}`;
                                removeBookmark(id);
                            } else {
                                addBookmark(cdk, state, year, crop);
                            }
                        }}
                        className={`flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-bold transition-all border shadow-sm ${isSaved
                            ? 'bg-emerald-50 text-emerald-600 border-emerald-200'
                            : 'bg-white text-slate-600 border-slate-200 hover:text-emerald-600 hover:border-emerald-200 hover:bg-emerald-50/50'
                            }`}
                    >
                        {isSaved ? <Check size={10} /> : <BookmarkIcon size={10} />}
                        {isSaved ? 'Saved' : 'Save'}
                    </button>
                </div>
            </div>

            {/* 1. Yield Efficiency */}
            {efficiency && efficiency.relative_efficiency && efficiency.historical_efficiency ? (
                <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4 transition-all duration-300 hover:shadow-md hover:border-emerald-200">
                    <h4 className="text-[10px] text-emerald-600 uppercase font-bold mb-4 flex items-center gap-2 tracking-wider">
                        <TrendingUp size={14} /> Efficiency Metrics
                    </h4>

                    {/* A. Relative Efficiency */}
                    <div className="mb-3 group/tooltip relative">
                        <div className="flex justify-between items-end mb-1">
                            <div>
                                <div className="text-xl font-bold text-slate-900">
                                    {(efficiency.relative_efficiency.efficiency_score * 100).toFixed(0)}%
                                </div>
                                <div className="text-[10px] text-slate-500 border-b border-dotted border-slate-600 cursor-help w-max">
                                    Relative (vs State)
                                </div>
                            </div>
                            <div className="text-right">
                                <div className="text-xs font-mono font-semibold text-rose-500">
                                    {efficiency.relative_efficiency.yield_gap_pct?.toFixed(1) || '0.0'}%
                                </div>
                                <div className="text-[10px] text-slate-500 font-medium">Gap</div>
                            </div>
                        </div>
                        <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden flex shadow-inner border border-slate-200/50">
                            <div
                                className="h-full bg-emerald-500"
                                style={{ width: `${Math.min((efficiency.relative_efficiency.efficiency_score || 0) * 100, 100)}%` }}
                            />
                        </div>

                        {/* Tooltip */}
                        <div className="absolute left-0 bottom-full mb-2 w-48 bg-slate-800 border border-slate-700 p-2 rounded text-[10px] text-slate-200 hidden group-hover/tooltip:block z-50 shadow-xl pointer-events-none">
                            <div className="font-bold text-emerald-400 mb-1">Relative Efficiency</div>
                            Compares yield ({efficiency.relative_efficiency.district_yield} kg/ha) to state top 5% ({efficiency.relative_efficiency.potential_yield} kg/ha).
                        </div>
                    </div>

                    {/* B. Historical Efficiency */}
                    <div className="group/tooltip relative">
                        <div className="flex justify-between items-end mb-1">
                            <div>
                                <div className={`text-xl font-bold ${efficiency.historical_efficiency.is_above_trend ? 'text-blue-600' : 'text-amber-600'}`}>
                                    {(efficiency.historical_efficiency.efficiency_ratio * 100).toFixed(0)}%
                                </div>
                                <div className="text-[10px] text-slate-500 border-b border-dotted border-slate-600 cursor-help w-max">
                                    Historical (vs 10y)
                                </div>
                            </div>
                            <div className="text-right">
                                <div className={`text-xs font-mono font-semibold ${efficiency.historical_efficiency.is_above_trend ? 'text-blue-600' : 'text-amber-600'}`}>
                                    {efficiency.historical_efficiency.yield_diff > 0 ? '+' : ''}{efficiency.historical_efficiency.yield_diff?.toFixed(1) || '0.0'}
                                </div>
                                <div className="text-[10px] text-slate-500 font-medium">Diff (kg/ha)</div>
                            </div>
                        </div>
                        <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden relative shadow-inner border border-slate-200/50">
                            <div className="absolute left-1/2 top-0 bottom-0 w-px bg-slate-300 z-10"></div>
                            <div
                                className={`h-full ${efficiency.historical_efficiency.is_above_trend ? 'bg-blue-500' : 'bg-amber-500'}`}
                                style={{
                                    width: `${Math.min(Math.abs((efficiency.historical_efficiency.efficiency_ratio || 1) - 1) * 100, 50)}%`,
                                    marginLeft: efficiency.historical_efficiency.is_above_trend ? '50%' : `${50 - Math.min(Math.abs((efficiency.historical_efficiency.efficiency_ratio || 1) - 1) * 100, 50)}%`
                                }}
                            />
                        </div>
                        {/* Tooltip */}
                        <div className="absolute left-0 bottom-full mb-2 w-48 bg-slate-800 border border-slate-700 p-2 rounded text-[10px] text-slate-200 hidden group-hover/tooltip:block z-50 shadow-xl pointer-events-none">
                            <div className="font-bold text-blue-400 mb-1">Historical Efficiency</div>
                            vs 10y Mean ({efficiency.historical_efficiency.historical_mean?.toFixed(1) || '?'} kg/ha).
                        </div>
                    </div>
                </div>
            ) : (
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 shadow-sm">
                    <div className="text-xs text-slate-500 text-center font-medium">Efficiency data unavailable</div>
                </div>
            )}

            {/* 2. Decision Intelligence (NEW) */}
            {
                riskData && riskData.resilience_index && riskData.growth_matrix ? (
                    <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4 transition-all duration-300 hover:shadow-md hover:border-indigo-200">
                        <h4 className="text-[10px] text-indigo-600 uppercase font-bold mb-4 flex items-center gap-2 tracking-wider">
                            <Shield size={14} /> Strategic Analysis
                        </h4>

                        {/* Resilience Score */}
                        <div className="flex justify-between items-center mb-4 pb-3 border-b border-slate-100">
                            <div>
                                <div className="text-[10px] text-slate-500 font-medium mb-1 flex items-center">
                                    Resilience Index
                                    <Tooltip text="Composite of Yield Stability and Drought Retention (0-100)" position="right" />
                                </div>
                                <div className="text-2xl font-bold text-slate-900">
                                    {(riskData.resilience_index.resilience_score * 100).toFixed(0)}
                                </div>
                            </div>
                            <div className="text-right">
                                <div className={`text-xs font-bold px-2 py-0.5 rounded border ${riskData.resilience_index.reliability_rating === 'A' ? 'border-emerald-200 text-emerald-700 bg-emerald-50' :
                                    riskData.resilience_index.reliability_rating === 'B' ? 'border-blue-200 text-blue-700 bg-blue-50' :
                                        'border-amber-200 text-amber-700 bg-amber-50'
                                    }`}>
                                    Grade {riskData.resilience_index.reliability_rating}
                                </div>
                            </div>
                        </div>

                        {/* Growth Matrix */}
                        <div className="flex justify-between items-center">
                            <div>
                                <div className="text-[10px] text-slate-500 font-medium mb-1 flex items-center">
                                    Growth Quadrant
                                    <Tooltip text="Classification based on 5-year CAGR and Yield Efficiency." position="right" />
                                </div>
                                <div className="text-sm font-bold text-slate-800">{riskData.growth_matrix.matrix_quadrant}</div>
                            </div>
                            <div className="text-right">
                                <div className="text-[10px] text-slate-500 font-medium">5y CAGR</div>
                                <div className={`text-xs font-mono font-semibold ${riskData.growth_matrix.cagr_5y > 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                                    {riskData.growth_matrix.cagr_5y > 0 ? '+' : ''}{riskData.growth_matrix.cagr_5y}%
                                </div>
                            </div>
                            <div className="text-right pl-4 border-l border-slate-200 ml-4 group/cagr relative">
                                <div className="text-[10px] text-slate-500 font-medium cursor-help border-b border-dotted border-slate-300">Hist. CAGR</div>
                                <div className={`text-xs font-mono font-semibold ${(riskData.growth_matrix.cagr_historical || 0) > 0 ? 'text-blue-600' : 'text-slate-500'}`}>
                                    {(riskData.growth_matrix.cagr_historical || 0) > 0 ? '+' : ''}{riskData.growth_matrix.cagr_historical}%
                                </div>
                                {/* Formula Tooltip */}
                                <div className="absolute right-0 bottom-full mb-2 w-48 bg-slate-800 border border-slate-700 p-2 rounded text-[10px] text-slate-200 hidden group-hover/cagr:block z-50 shadow-xl pointer-events-none">
                                    <div className="font-bold text-slate-300 mb-1">CAGR Formula</div>
                                    <code className="text-[9px] font-mono text-emerald-400 block mb-1">
                                        {riskData.growth_matrix.formula || "((End/Start)^(1/n) - 1) * 100"}
                                    </code>
                                    <div className="text-slate-400 italic">Compound Annual Growth Rate</div>
                                </div>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 shadow-sm">
                        <div className="text-xs text-slate-500 text-center font-medium">Strategic Analysis unavailable</div>
                    </div>
                )
            }

            {/* 3. Risk Profile (Detailed) */}
            {
                risk && (
                    <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4 transition-all duration-300 hover:shadow-md hover:border-rose-200">
                        <h4 className="text-[10px] text-slate-500 uppercase font-bold mb-3 flex items-center gap-2 tracking-wider">
                            <AlertTriangle size={14} className="text-rose-500" /> Risk Details
                        </h4>

                        <div className="flex items-center gap-3">
                            <div className={`px-2 py-1 rounded text-xs font-bold uppercase border bg-white ${risk.risk_category === 'low' ? 'border-emerald-200 text-emerald-600' :
                                risk.risk_category === 'medium' ? 'border-amber-200 text-amber-600' :
                                    'border-rose-200 text-rose-600'
                                }`}>
                                {risk.risk_category} Risk
                            </div>

                            <div className="flex-1 text-right border-l border-slate-100 pl-3">
                                <div className="text-xs font-medium text-slate-700 flex justify-end items-center">
                                    {risk.trend_stability}
                                    <Tooltip text="Overall directional stability of the historical yield." position="left" />
                                </div>
                                <div className="text-[10px] text-slate-500 mt-1 flex justify-end items-center">
                                    CV: <span className="font-mono ml-1">{risk.volatility_score?.toFixed(1) || '?'}%</span>
                                    <Tooltip text="Coefficient of Variation. Higher = more unpredictable yields." position="left" />
                                </div>
                            </div>
                        </div>
                    </div>
                )
            }

            {/* 3. Crop Diversification */}
            {
                diversification && diversification.cdi !== undefined && (
                    <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4 transition-all duration-300 hover:shadow-md hover:border-purple-200">
                        <h4 className="text-[10px] text-purple-600 uppercase font-bold mb-3 flex items-center gap-2 tracking-wider">
                            <PieChart size={14} /> State Diversity
                            <Tooltip text="Simpson's Diversity Index (0-1). 1 = highly diverse, 0 = monoculture." position="right" />
                        </h4>

                        <div className="flex justify-between items-center mb-2">
                            <span className="text-xl font-bold text-slate-900">{diversification.cdi.toFixed(2)}</span>
                            <span className="text-[10px] text-right text-slate-500 font-medium max-w-[120px] leading-tight">
                                {diversification.interpretation}
                            </span>
                        </div>

                        {/* Dominant Crop */}
                        <div className="text-xs text-slate-500 border-t border-slate-100 pt-2 mt-2">
                            Dominant: <span className="text-slate-800 font-medium capitalize">{diversification.dominant_crop?.replace(/_/g, ' ') || 'Unknown'}</span>
                            <span className="text-slate-500 font-mono text-[10px] ml-1">({diversification.breakdown && diversification.dominant_crop ? (diversification.breakdown[diversification.dominant_crop] * 100).toFixed(1) : '?'}%)</span>
                        </div>
                    </div>
                )
            }

            {/* 4. Climate Correlation */}
            {
                correlation && (
                    <ClimateCorrelationCard data={correlation} crop={crop} />
                )
            }
            {/* 5. Simulation (New) */}
            {districtName && state && (
                <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4 mt-2 transition-all duration-300 hover:shadow-md hover:border-indigo-200">
                    <h4 className="text-[10px] text-indigo-600 uppercase font-bold mb-4 flex items-center gap-2 tracking-wider">
                        <Calculator size={14} /> Impact Simulator
                    </h4>
                    <SimulationPanel district={districtName} state={state} crop={crop} year={year} />
                </div>
            )}
        </div >
    );
}
