
"use client";
import React from 'react';
import { History, Network } from 'lucide-react';
import { AnalysisMode } from '../../services/api';

interface ComparisonModeSelectorProps {
    mode: AnalysisMode;
    onChange: (m: AnalysisMode) => void;
}

export function ComparisonModeSelector({ mode, onChange }: ComparisonModeSelectorProps) {
    const modes: Array<{ id: AnalysisMode; label: string; fullLabel: string; icon: typeof History }> = [
        { id: 'before_after', label: 'Before vs After', fullLabel: 'Before vs After (Reconstructed)', icon: History },
        { id: 'entity_comparison', label: 'Parent vs Child', fullLabel: 'Parent vs Child', icon: Network },
    ];

    return (
        <div className="flex gap-1 md:gap-2 bg-slate-100 p-1.5 rounded-xl mb-3 md:mb-4 border border-slate-200">
            {modes.map(m => (
                <button
                    key={m.id}
                    onClick={() => onChange(m.id)}
                    className={`flex-1 flex items-center justify-center gap-1 md:gap-2 py-2 px-2 md:px-3 text-[10px] md:text-xs font-semibold rounded-lg transition-all duration-300
                        ${mode === m.id
                            ? 'bg-white text-indigo-700 shadow-sm border border-slate-200/60'
                            : 'text-slate-500 hover:text-slate-800 hover:bg-slate-200/50'
                        }`}
                >
                    <m.icon size={12} className="md:w-[14px] md:h-[14px]" />
                    <span className="hidden sm:inline">{m.fullLabel}</span>
                    <span className="sm:hidden">{m.label}</span>
                </button>
            ))}
        </div>
    );
}
