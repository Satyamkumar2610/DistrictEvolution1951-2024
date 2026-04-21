import React from 'react';
import { Sparkles } from 'lucide-react';

interface AINarrativeProps {
    narrative: string | null | undefined;
}

export function AINarrative({ narrative }: AINarrativeProps) {
    if (!narrative) return null;

    return (
        <div className="bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-100 rounded-xl p-5 shadow-sm mt-4 mb-4 relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-10">
                <Sparkles size={64} className="text-indigo-600" />
            </div>
            <div className="relative z-10">
                <div className="flex items-center gap-2 mb-2">
                    <div className="bg-indigo-100 p-1.5 rounded-lg">
                        <Sparkles size={16} className="text-indigo-600" />
                    </div>
                    <h3 className="text-sm font-bold text-indigo-900">AI Analyst Insight</h3>
                </div>
                <p className="text-sm text-slate-700 leading-relaxed max-w-4xl">
                    {narrative}
                </p>
            </div>
        </div>
    );
}
