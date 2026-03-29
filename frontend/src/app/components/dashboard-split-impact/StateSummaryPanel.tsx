
"use client";

import React from 'react';
import { Map, AlertTriangle, Layers, Database } from 'lucide-react';
import { StateSummary } from '../../services/api';

// Static color map for light theme
const COLOR_MAP: Record<string, { bg: string; text: string; iconBg: string }> = {
    blue: { bg: 'bg-white', text: 'text-indigo-600', iconBg: 'bg-indigo-50' },
    amber: { bg: 'bg-white', text: 'text-amber-600', iconBg: 'bg-amber-50' },
    purple: { bg: 'bg-white', text: 'text-purple-600', iconBg: 'bg-purple-50' },
    emerald: { bg: 'bg-white', text: 'text-emerald-600', iconBg: 'bg-emerald-50' },
};

interface StateSummaryPanelProps {
    stateName: string;
    stats: StateSummary['stats'][string] | null;
}

export function StateSummaryPanel({ stateName, stats }: StateSummaryPanelProps) {
    if (!stats || !stateName) return null;

    const cards = [
        {
            icon: Map,
            color: 'blue',
            label: 'Total Districts',
            value: stats.total,
            subtitle: null,
        },
        {
            icon: AlertTriangle,
            color: 'amber',
            label: 'Boundary Changes',
            value: stats.changed,
            subtitle: 'Districts impacted by splits',
        },
        {
            icon: Database,
            color: 'purple',
            label: 'Data Coverage',
            value: 'High',
            subtitle: 'V1.5 Harmonized Panel',
        },
        {
            icon: Layers,
            color: 'emerald',
            label: 'Comparability',
            value: stats.changed > 0 ? 'Active' : 'N/A',
            subtitle: null,
            faded: true,
        },
    ];

    return (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-4 mb-4 md:mb-8 min-w-[280px]">
            {cards.map((card, idx) => {
                const colors = COLOR_MAP[card.color] || COLOR_MAP.blue;
                return (
                    <div
                        key={idx}
                        className={`bg-white p-3 md:p-4 rounded-lg md:rounded-xl transition-all hover:shadow-md border border-slate-200 shadow-sm ${card.faded ? 'opacity-50 grayscale' : ''}`}
                    >
                        <div className="flex items-center gap-2 md:gap-3 mb-1">
                            <div className={`p-1.5 md:p-2 ${colors.iconBg} rounded-md md:rounded-lg`}>
                                <card.icon className={`${colors.text} w-3.5 h-3.5 md:w-[18px] md:h-[18px]`} />
                            </div>
                            <span className="text-slate-500 text-[9px] md:text-xs font-bold uppercase tracking-wider truncate">
                                {card.label}
                            </span>
                        </div>
                        <div className="text-lg md:text-2xl font-bold text-slate-900 pl-1">{card.value}</div>
                        {card.subtitle && (
                            <div className="text-[9px] md:text-[10px] text-slate-500 mt-1 pl-1 hidden sm:block font-medium">
                                {card.subtitle}
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
