"use client";
import React from 'react';
import { Info } from 'lucide-react';
import { AnalysisMode, SplitDistrict } from '../../services/api';

interface ComparisonContextBannerProps {
    event: SplitDistrict;
    mode: AnalysisMode;
}

export function ComparisonContextBanner({ event, mode }: ComparisonContextBannerProps) {
    if (!event) return null;

    return (
        <div className="mb-3 md:mb-4 bg-indigo-50/50 border border-indigo-100 border-l-4 border-l-indigo-500 p-3 md:p-4 rounded-r-xl shadow-sm">
            <h4 className="text-[10px] md:text-xs font-bold text-indigo-600 uppercase tracking-widest mb-2 flex items-center gap-1.5 md:gap-2">
                <Info size={12} className="md:w-[14px] md:h-[14px]" />
                Analysis Context
            </h4>
            <div className="grid grid-cols-2 gap-2 md:gap-4 text-[10px] md:text-xs">
                {/* Row 1 */}
                <div>
                    <span className="text-slate-500 block font-medium">Comparison Type</span>
                    <span className="text-slate-800 font-mono font-semibold truncate block">
                        {mode === 'before_after' ? 'Longitudinal' : 'Entity Comparison'}
                    </span>
                </div>
                <div>
                    <span className="text-slate-500 block font-medium">Parent District</span>
                    <span className="text-slate-900 font-bold truncate block">
                        {event.parent_name}
                        <span className="text-slate-500 ml-1 hidden sm:inline font-normal">(Pre-{event.split_year})</span>
                    </span>
                </div>

                {/* Row 2 */}
                <div className="col-span-2 sm:col-span-1">
                    <span className="text-slate-500 block font-medium">Descendants</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                        {event.children_names && event.children_names.slice(0, 3).map((c: string) => (
                            <span key={c} className="bg-white border border-slate-200 shadow-sm px-1.5 py-0.5 rounded text-indigo-700 font-medium text-[9px] md:text-xs truncate max-w-[80px] md:max-w-none">
                                {c}
                            </span>
                        ))}
                        {event.children_names && event.children_names.length > 3 && (
                            <span className="text-slate-500 font-medium bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">+{event.children_names.length - 3}</span>
                        )}
                    </div>
                </div>

                <div className="hidden sm:block">
                    <span className="text-slate-500 block font-medium">Fragmentation Index</span>
                    <span className="text-slate-800 flex items-center gap-1 font-mono font-bold">
                        {event.children_names ? (event.children_names.length / 1.0).toFixed(1) : '0.0'}
                        <span className="text-slate-500 text-[10px] ml-1 font-sans font-normal">splits/parent</span>
                    </span>
                </div>
            </div>
        </div>
    );
}
