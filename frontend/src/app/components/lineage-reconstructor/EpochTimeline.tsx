import React from 'react';

import type { LineageReconstructionEpoch } from '@/app/services/api/types';

export default function EpochTimeline({ 
    epochs, 
    activeEpochIndex, 
    onEpochChange 
}: { 
    epochs: LineageReconstructionEpoch[], 
    activeEpochIndex: number, 
    onEpochChange: (index: number) => void 
}) {
    if (!epochs || epochs.length === 0) return null;

    const minYear = epochs[0].year_start;
    const maxYear = 2024;
    const span = maxYear - minYear;

    return (
        <div className="w-full bg-slate-900/60 backdrop-blur border border-slate-800/50 rounded-2xl p-5 relative">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Epoch Timeline</h3>
                <div className="flex items-center gap-3 text-[10px] text-slate-600">
                    <span className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full bg-violet-500 inline-block shadow-sm shadow-violet-500/30" />
                        Active
                    </span>
                    <span className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full bg-slate-700 inline-block" />
                        Other
                    </span>
                    <span className="flex items-center gap-1.5">
                        <span className="w-3 h-0.5 bg-amber-500 rounded inline-block" />
                        Split Event
                    </span>
                </div>
            </div>
            
            {/* Timeline track */}
            <div className="relative h-3 bg-slate-800 rounded-full w-full flex overflow-hidden">
                {epochs.map((ep, idx) => {
                    const startYear = ep.year_start;
                    const endYear = ep.year_end || maxYear;
                    const widthPercent = ((endYear - startYear + 1) / span) * 100;
                    const isActive = idx === activeEpochIndex;

                    return (
                        <div 
                            key={idx}
                            onClick={() => onEpochChange(idx)}
                            className={`h-full cursor-pointer transition-all duration-300 relative group
                                ${idx > 0 ? 'border-l-2 border-slate-950' : ''}
                                ${isActive 
                                    ? 'bg-gradient-to-r from-violet-500 to-indigo-500 shadow-inner' 
                                    : 'bg-slate-700/50 hover:bg-slate-600/50'}`}
                            style={{ width: `${widthPercent}%` }}
                        >
                            {/* Glow effect on active */}
                            {isActive && (
                                <div className="absolute inset-0 bg-gradient-to-r from-violet-500/20 to-indigo-500/20 blur-md -z-10" />
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Event markers and labels */}
            <div className="relative mt-3 h-12">
                {epochs.map((ep, idx) => {
                    const startYear = ep.year_start;
                    const endYear = ep.year_end || maxYear;
                    const midPoint = ((((startYear + endYear) / 2) - minYear) / span) * 100;
                    const leftPos = (((startYear) - minYear) / span) * 100;
                    const isActive = idx === activeEpochIndex;

                    return (
                        <React.Fragment key={idx}>
                            {/* Split marker */}
                            {idx > 0 && (
                                <div 
                                    className="absolute top-0 flex flex-col items-center -translate-x-1/2"
                                    style={{ left: `${leftPos}%` }}
                                >
                                    <div className="w-2.5 h-2.5 rounded-full bg-amber-500 shadow-md shadow-amber-500/30 ring-2 ring-amber-500/20 animate-pulse" />
                                    <span className="text-[10px] font-bold text-amber-400/80 mt-1 whitespace-nowrap">{startYear}</span>
                                </div>
                            )}

                            {/* Epoch label */}
                            <div
                                className="absolute bottom-0 -translate-x-1/2 text-center"
                                style={{ left: `${midPoint}%` }}
                            >
                                <span className={`text-[10px] font-medium whitespace-nowrap
                                    ${isActive ? 'text-violet-300' : 'text-slate-600'}`}>
                                    {isActive ? `Epoch ${ep.epoch_num}` : `E${ep.epoch_num}`}
                                </span>
                            </div>

                            {/* Event label (on hover / always for active) */}
                            {isActive && ep.event_label && idx > 0 && (
                                <div
                                    className="absolute -top-1 px-2 py-0.5 bg-slate-800/90 border border-slate-700/50 rounded text-[9px] text-slate-400 whitespace-nowrap backdrop-blur"
                                    style={{ left: `${leftPos + 2}%` }}
                                >
                                    {ep.event_label}
                                </div>
                            )}
                        </React.Fragment>
                    );
                })}
            </div>
            
            {/* Year range */}
            <div className="flex justify-between mt-1">
                <span className="text-[10px] font-mono text-slate-600">{minYear}</span>
                <span className="text-[10px] font-mono text-slate-600">{maxYear}</span>
            </div>
        </div>
    );
}
