import React from 'react';

export default function EpochTimeline({ 
    epochs, 
    activeEpochIndex, 
    onEpochChange 
}: { 
    epochs: any[], 
    activeEpochIndex: number, 
    onEpochChange: (index: number) => void 
}) {
    if (!epochs || epochs.length === 0) return null;

    const minYear = epochs[0].year_start;
    const maxYear = 2024; // standard UI boundary for this app
    const span = maxYear - minYear;

    return (
        <div className="w-full bg-white border border-slate-200 rounded-lg p-6 shadow-sm relative pt-12">
            <h3 className="absolute top-4 left-6 text-sm font-bold text-slate-700 uppercase tracking-wide">Epoch Timeline</h3>
            
            {/* Base timeline track */}
            <div className="relative h-2 bg-slate-200 rounded-full w-full mt-4 flex">
                
                {epochs.map((ep, idx) => {
                    const startYear = ep.year_start;
                    const endYear = ep.year_end || maxYear;
                    const widthPercent = ((endYear - startYear + 1) / span) * 100;
                    const isActive = idx === activeEpochIndex;

                    return (
                        <div 
                            key={idx}
                            onClick={() => onEpochChange(idx)}
                            className={`h-full cursor-pointer transition-colors border-r border-white relative group
                                ${isActive ? 'bg-indigo-500' : 'bg-slate-300 hover:bg-slate-400'}`}
                            style={{ width: `${widthPercent}%` }}
                        >
                            {/* Pin for Split Event */}
                            {idx > 0 && (
                                <div className="absolute left-0 top-0 -translate-x-1/2 -translate-y-full pb-4 flex flex-col items-center">
                                    <span className="text-xs font-bold text-slate-700">{startYear}</span>
                                    <div className="w-0.5 h-3 bg-slate-400 mt-1"></div>
                                    <div className="absolute top-8 whitespace-nowrap text-[10px] text-slate-500 font-medium bg-white px-1.5 py-0.5 border border-slate-200 rounded shadow-sm opacity-0 group-hover:opacity-100 transition">
                                        {ep.event_label}
                                    </div>
                                </div>
                            )}

                            {/* Active segment label */}
                            {isActive && (
                                <div className="absolute left-1/2 top-4 -translate-x-1/2 whitespace-nowrap text-[11px] font-semibold text-indigo-600">
                                    Epoch {ep.epoch_num}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
            
            <div className="flex justify-between mt-4">
                <span className="text-xs font-semibold text-slate-400">{minYear}</span>
                <span className="text-xs font-semibold text-slate-400">{maxYear}</span>
            </div>
        </div>
    );
}
