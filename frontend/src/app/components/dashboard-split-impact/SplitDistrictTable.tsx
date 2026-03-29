import React, { useMemo, useState } from 'react';
import { ArrowRight, CheckCircle2, AlertTriangle } from 'lucide-react';
import { SplitDistrict } from '../../services/api';

interface SplitDistrictTableProps {
    splits: SplitDistrict[];
    onSelect?: (event: SplitDistrict) => void;
    selectedEventId?: string;
    isLoading?: boolean;
}

export default function SplitDistrictTable({ splits, onSelect, selectedEventId, isLoading }: SplitDistrictTableProps) {
    const [activeDecade, setActiveDecade] = useState<string | null>(null);

    // Derive available decades from the split events
    const decades = useMemo(() => {
        if (!splits || splits.length === 0) return [];
        const ds = new Set<string>();
        for (const s of splits) {
            const decade = `${Math.floor(s.split_year / 10) * 10}s`;
            ds.add(decade);
        }
        return Array.from(ds).sort();
    }, [splits]);

    // Filter by selected decade
    const filtered = useMemo(() => {
        if (!splits) return [];
        if (!activeDecade) return splits;
        const decadeStart = parseInt(activeDecade);
        return splits.filter((s) => {
            const yr = s.split_year;
            return yr >= decadeStart && yr < decadeStart + 10;
        });
    }, [splits, activeDecade]);

    if (isLoading) return <div className="text-xs text-slate-500 italic p-4">Analyzing district split lineage...</div>;

    if (!splits || splits.length === 0) return <div className="p-4 text-xs text-slate-500">No split events found for this state.</div>;

    return (
        <div className="space-y-3">
            {/* Decade filter pills */}
            {decades.length > 1 && (
                <div className="flex flex-wrap gap-1.5 pb-2 border-b border-slate-200">
                    <button
                        onClick={() => setActiveDecade(null)}
                        className={`px-2.5 py-1 rounded-full text-[10px] font-bold transition-colors ${!activeDecade
                            ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                            : 'bg-slate-50 text-slate-600 border border-slate-200 hover:border-slate-300'
                            }`}
                    >
                        All ({splits.length})
                    </button>
                    {decades.map(d => {
                        const decadeStart = parseInt(d);
                        const count = splits.filter((s) => s.split_year >= decadeStart && s.split_year < decadeStart + 10).length;
                        return (
                            <button
                                key={d}
                                onClick={() => setActiveDecade(activeDecade === d ? null : d)}
                                className={`px-2.5 py-1 rounded-full text-[10px] font-bold transition-colors ${activeDecade === d
                                    ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                                    : 'bg-slate-50 text-slate-600 border border-slate-200 hover:border-slate-300'
                                    }`}
                            >
                                {d} ({count})
                            </button>
                        );
                    })}
                </div>
            )}

            {/* Split event cards */}
            {filtered.map((item) => {
                const resolvedCount = item.resolved_count ?? item.children_cdks?.filter((c: string | null) => c != null).length ?? 0;
                const totalCount = item.total_count ?? item.children_cdks?.length ?? 0;
                const allResolved = resolvedCount === totalCount && totalCount > 0;

                return (
                    <div
                        key={item.id}
                        onClick={() => onSelect && onSelect(item)}
                        className={`p-3 rounded-lg border cursor-pointer transition-all shadow-sm ${selectedEventId === item.id
                            ? 'bg-indigo-50 border-indigo-300 ring-1 ring-indigo-300'
                            : 'bg-white border-slate-200 hover:border-indigo-200 hover:shadow-md'
                            }`}
                    >
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                                <span className={`text-sm font-bold ${selectedEventId === item.id ? 'text-indigo-900' : 'text-slate-800'}`}>
                                    {item.parent_name}
                                </span>
                                <ArrowRight size={12} className="text-slate-600" />
                                <span className="text-xs text-slate-500 font-medium">Split in {item.split_year}</span>
                            </div>
                            {/* Resolution badge */}
                            {allResolved ? (
                                <span title="All districts resolved"><CheckCircle2 size={14} className="text-emerald-500 shrink-0" /></span>
                            ) : (
                                <span title={`${resolvedCount}/${totalCount} resolved`}><AlertTriangle size={14} className="text-amber-500 shrink-0" /></span>
                            )}
                        </div>

                        <div className="space-y-1 pl-4 border-l-2 border-slate-200">
                            {item.children_names && Array.isArray(item.children_names) ? (
                                item.children_names.map((childName: string, idx: number) => {
                                    const isRetainedParent = childName === item.parent_name;
                                    return (
                                        <div key={`${childName}-${idx}`} className="flex items-center gap-1.5 text-xs">
                                            {isRetainedParent ? (
                                                <>
                                                    <span className="text-slate-500">{childName}</span>
                                                    <span className="text-[9px] text-slate-500 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded font-medium">retained</span>
                                                </>
                                            ) : (
                                                <span className="text-indigo-600 font-medium">{childName}</span>
                                            )}
                                        </div>
                                    );
                                })
                            ) : (
                                <span className="text-xs text-slate-500">No children data</span>
                            )}
                        </div>
                    </div>
                );
            })}

            {filtered.length === 0 && activeDecade && (
                <div className="p-4 text-xs text-slate-500 text-center">
                    No split events in the {activeDecade}.
                </div>
            )}
        </div>
    );
}
