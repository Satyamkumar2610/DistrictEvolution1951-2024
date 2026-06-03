import React from 'react';
import { Shield, AlertTriangle, Scale, MapPin } from 'lucide-react';
import { AnalysisMaupInsights } from '../../services/api';

export function MaupReliabilityPanel({ maup }: { maup?: AnalysisMaupInsights }) {
    if (!maup) return null;

    const isVulnerable = maup.zoning.is_sensitive || maup.scale.is_smoothing;

    return (
        <div className={`mt-4 mb-4 p-4 rounded-xl border shadow-sm animate-in fade-in ${
            isVulnerable ? 'bg-rose-50 border-rose-200' : 'bg-emerald-50 border-emerald-200'
        }`}>
            <div className="flex items-center gap-2 mb-3">
                {isVulnerable ? <AlertTriangle className="text-rose-600" size={20} /> : <Shield className="text-emerald-600" size={20} />}
                <h4 className={`font-bold ${isVulnerable ? 'text-rose-800' : 'text-emerald-800'}`}>
                    MAUP Reliability Assessment
                </h4>
                <span className={`text-xs px-2 py-0.5 rounded-full ml-auto font-bold ${
                    isVulnerable ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-700'
                }`}>
                    {maup.overall_reliability}
                </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Zoning Sensitivity */}
                <div className="bg-white/60 p-3 rounded-lg border border-white/20">
                    <h5 className="flex items-center gap-1.5 text-sm font-bold text-slate-800 mb-1">
                        <MapPin size={14} className="text-indigo-600" /> 
                        Zoning Sensitivity
                    </h5>
                    <p className="text-xs text-slate-600 mb-2">
                        {maup.zoning.interpretation}
                    </p>
                    {maup.zoning.plain_english && (
                        <p className="text-[10px] text-slate-500 mb-2 italic">
                            {maup.zoning.plain_english}
                        </p>
                    )}
                    <div className="flex items-center gap-2">
                        <span className="text-lg font-black text-slate-800">
                            {maup.zoning.divergence_score}%
                        </span>
                        <span className="text-[10px] text-slate-500 font-medium">divergence</span>
                    </div>
                </div>

                {/* Scale Effect */}
                <div className="bg-white/60 p-3 rounded-lg border border-white/20">
                    <h5 className="flex items-center gap-1.5 text-sm font-bold text-slate-800 mb-1">
                        <Scale size={14} className="text-indigo-600" /> 
                        Scale Effect
                    </h5>
                    <p className="text-xs text-slate-600 mb-2">
                        {maup.scale.interpretation}
                    </p>
                    {maup.scale.plain_english && (
                        <p className="text-[10px] text-slate-500 mb-2 italic">
                            {maup.scale.plain_english}
                        </p>
                    )}
                    <div className="flex items-center gap-2">
                        <span className="text-lg font-black text-slate-800">
                            {maup.scale.variance_difference > 0 ? '+' : ''}{maup.scale.variance_difference}%
                        </span>
                        <span className="text-[10px] text-slate-500 font-medium">variance difference</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
