"use client";

import React, { useEffect, useState } from 'react';
import { GitBranch, Calendar, MapPin, TrendingUp, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';

interface TransitionEvent {
    from_district: string;
    to_district: string;
    transition_type: string;
    effective_date: string;
    area_weight: number;
    confidence: number;
}

interface LineageData {
    unit_id: string;
    unit_name: string;
    state: string;
    valid_from: string;
    valid_to: string | null;
    ancestors: TransitionEvent[];
    descendants: TransitionEvent[];
}

interface LineagePanelProps {
    unitId: string | null;
    apiBaseUrl?: string;
    onClose?: () => void;
}

function formatDate(dateStr: string): string {
    if (!dateStr) return '—';
    try {
        return new Date(dateStr).toLocaleDateString('en-IN', {
            day: 'numeric',
            month: 'short',
            year: 'numeric',
        });
    } catch {
        return dateStr;
    }
}

function confidenceColor(confidence: number): string {
    if (confidence >= 0.8) return 'text-emerald-400';
    if (confidence >= 0.5) return 'text-amber-400';
    return 'text-red-400';
}

function confidenceLabel(confidence: number): string {
    if (confidence >= 0.8) return 'High';
    if (confidence >= 0.5) return 'Medium';
    return 'Low';
}

function transitionTypeLabel(type: string): string {
    const labels: Record<string, string> = {
        SPLIT: 'Split',
        MERGE: 'Merged',
        RENAME: 'Renamed',
        BOUNDARY_ADJUST: 'Boundary adjusted',
    };
    return labels[type] || type;
}

export default function LineagePanel({ unitId, apiBaseUrl = '', onClose }: LineagePanelProps) {
    const [data, setData] = useState<LineageData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showAncestors, setShowAncestors] = useState(true);
    const [showDescendants, setShowDescendants] = useState(true);

    useEffect(() => {
        if (!unitId) {
            setData(null);
            return;
        }

        setLoading(true);
        setError(null);

        fetch(`${apiBaseUrl}/api/v1/lineage/${unitId}`)
            .then(res => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.json();
            })
            .then(json => setData(json))
            .catch(err => setError(err.message))
            .finally(() => setLoading(false));
    }, [unitId, apiBaseUrl]);

    if (!unitId) return null;

    return (
        <div className="bg-slate-900/95 backdrop-blur-md border border-slate-700 rounded-xl p-4 shadow-2xl w-80 max-h-[500px] overflow-y-auto text-sm">
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <GitBranch size={16} className="text-violet-400" />
                    <span className="text-[10px] font-bold uppercase tracking-widest text-violet-400">
                        District Lineage
                    </span>
                </div>
                {onClose && (
                    <button
                        onClick={onClose}
                        className="text-slate-500 hover:text-slate-300 transition-colors text-xs"
                        aria-label="Close lineage panel"
                    >
                        ✕
                    </button>
                )}
            </div>

            {loading && (
                <div className="flex items-center gap-2 text-slate-400 py-8 justify-center">
                    <div className="w-4 h-4 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
                    <span>Loading lineage...</span>
                </div>
            )}

            {error && (
                <div className="text-red-400 text-xs py-4 text-center">
                    Failed to load lineage: {error}
                </div>
            )}

            {data && (
                <>
                    {/* District Info */}
                    <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-3 mb-3">
                        <h3 className="font-bold text-slate-100 text-base">
                            {data.unit_name}
                        </h3>
                        <div className="flex items-center gap-1.5 mt-1">
                            <MapPin size={12} className="text-slate-500" />
                            <span className="text-slate-400 text-xs">{data.state}</span>
                        </div>
                        <div className="flex items-center gap-1.5 mt-1">
                            <Calendar size={12} className="text-slate-500" />
                            <span className="text-slate-400 text-xs">
                                {formatDate(data.valid_from)} → {data.valid_to ? formatDate(data.valid_to) : 'present'}
                            </span>
                        </div>
                    </div>

                    {/* Ancestors */}
                    {data.ancestors.length > 0 && (
                        <div className="mb-3">
                            <button
                                onClick={() => setShowAncestors(!showAncestors)}
                                className="flex items-center justify-between w-full text-left py-1.5"
                            >
                                <span className="text-[10px] font-bold uppercase tracking-widest text-amber-400">
                                    Formed from
                                </span>
                                {showAncestors ? (
                                    <ChevronUp size={14} className="text-slate-500" />
                                ) : (
                                    <ChevronDown size={14} className="text-slate-500" />
                                )}
                            </button>
                            {showAncestors && (
                                <div className="space-y-2 mt-1">
                                    {data.ancestors.map((event, i) => (
                                        <div
                                            key={i}
                                            className="bg-slate-800/40 border border-slate-700/60 rounded-lg p-2.5"
                                        >
                                            <div className="font-medium text-slate-200">
                                                {event.from_district}
                                            </div>
                                            <div className="text-xs text-slate-500 mt-1 space-y-0.5">
                                                <div>
                                                    {transitionTypeLabel(event.transition_type)} on{' '}
                                                    {formatDate(event.effective_date)}
                                                </div>
                                                <div className="flex items-center gap-3">
                                                    <span>
                                                        Area share:{' '}
                                                        <span className="text-slate-300 font-medium">
                                                            {Math.round(event.area_weight * 100)}%
                                                        </span>
                                                    </span>
                                                    <span className="flex items-center gap-1">
                                                        Confidence:{' '}
                                                        <span className={`font-medium ${confidenceColor(event.confidence)}`}>
                                                            {confidenceLabel(event.confidence)}
                                                        </span>
                                                        {event.confidence < 0.5 && (
                                                            <AlertTriangle size={10} className="text-red-400" />
                                                        )}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Descendants */}
                    {data.descendants.length > 0 && (
                        <div>
                            <button
                                onClick={() => setShowDescendants(!showDescendants)}
                                className="flex items-center justify-between w-full text-left py-1.5"
                            >
                                <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-400">
                                    Split into
                                </span>
                                {showDescendants ? (
                                    <ChevronUp size={14} className="text-slate-500" />
                                ) : (
                                    <ChevronDown size={14} className="text-slate-500" />
                                )}
                            </button>
                            {showDescendants && (
                                <div className="space-y-2 mt-1">
                                    {data.descendants.map((event, i) => (
                                        <div
                                            key={i}
                                            className="bg-slate-800/40 border border-slate-700/60 rounded-lg p-2.5"
                                        >
                                            <div className="flex items-center gap-1.5">
                                                <TrendingUp size={12} className="text-emerald-400" />
                                                <span className="font-medium text-slate-200">
                                                    {event.to_district}
                                                </span>
                                            </div>
                                            <div className="text-xs text-slate-500 mt-1 space-y-0.5">
                                                <div>
                                                    {transitionTypeLabel(event.transition_type)} on{' '}
                                                    {formatDate(event.effective_date)}
                                                </div>
                                                <div>
                                                    Area share:{' '}
                                                    <span className="text-slate-300 font-medium">
                                                        {Math.round(event.area_weight * 100)}%
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {/* No lineage data */}
                    {data.ancestors.length === 0 && data.descendants.length === 0 && (
                        <div className="text-slate-500 text-xs text-center py-4">
                            No boundary changes recorded for this district.
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
