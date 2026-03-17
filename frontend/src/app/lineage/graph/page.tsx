'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import ReactECharts from 'echarts-for-react';
import { api } from '../../services/api';
import { GitBranch, Database, MapPin, Search, ArrowRight, Info, Table as TableIcon, Activity } from 'lucide-react';

interface SplitEvent {
    state_name: string;
    split_year: number;
    parent_district: string;
    child_district: string;
    parent_cdk: string;
    child_cdk: string;
    source: string;
}

export default function LineagePage() {
    const [selectedState, setSelectedState] = useState<string>('');
    const [selectedCdk, setSelectedCdk] = useState<string>('');
    const [coverageSearch, setCoverageSearch] = useState('');
    const [viewMode, setViewMode] = useState<'graph' | 'table'>('graph');

    const { data: states, isLoading: isLoadingStates, isError: isStatesError } = useQuery({
        queryKey: ['states-list'],
        queryFn: () => api.getStatesList(),
    });

    const { data: history, isLoading: isLoadingHistory, isError: isHistoryError } = useQuery({
        queryKey: ['lineage-history', selectedState],
        queryFn: () => api.getLineageHistory(selectedState),
        enabled: !!selectedState,
    });

    const { data: tracking } = useQuery({
        queryKey: ['lineage-tracking', selectedCdk],
        queryFn: () => api.getDataTracking(selectedCdk),
        enabled: !!selectedCdk,
    });

    const { data: coverage, isLoading: isLoadingCoverage, isError: isCoverageError } = useQuery({
        queryKey: ['state-coverage', selectedState],
        queryFn: () => api.getStateCoverage(selectedState),
        enabled: !!selectedState,
    });

    const hasErrors = isStatesError || isHistoryError || isCoverageError;

    // Group history by decade
    const decades = useMemo(() => {
        if (!history) return {};
        const grouped: Record<number, SplitEvent[]> = {};
        history.forEach((event: SplitEvent) => {
            const decade = Math.floor(event.split_year / 10) * 10;
            if (!grouped[decade]) grouped[decade] = [];
            grouped[decade].push(event);
        });
        return grouped;
    }, [history]);

    // Summary stats
    const summaryStats = useMemo(() => {
        if (!history || history.length === 0) return null;
        const years = history.map((e: SplitEvent) => e.split_year);
        const parents = new Set(history.map((e: SplitEvent) => e.parent_district));
        return {
            totalEvents: history.length,
            timeSpan: `${Math.min(...years)}–${Math.max(...years)}`,
            uniqueParents: parents.size,
            decadeCount: Object.keys(decades).length,
        };
    }, [history, decades]);

    // Reset selectedCdk and coverageSearch when state changes
    useEffect(() => {
        setSelectedCdk('');
        setCoverageSearch('');
    }, [selectedState]);

    // Construct Graph Data
    const graphData = useMemo(() => {
        if (!history || history.length === 0) return null;

        const nodes: any[] = []; /* eslint-disable-line @typescript-eslint/no-explicit-any */
        const links: any[] = []; /* eslint-disable-line @typescript-eslint/no-explicit-any */
        const uniqueNodes = new Set<string>();

        // Set up root and derived districts based on split year and edges
        history.forEach((event: SplitEvent) => {
            if (!uniqueNodes.has(event.parent_district)) {
                uniqueNodes.add(event.parent_district);
                nodes.push({
                    id: event.parent_district,
                    name: event.parent_district,
                    symbolSize: 45,
                    itemStyle: {
                        color: '#8B5CF6',
                        borderColor: '#ffffff',
                        borderWidth: 3,
                        shadowBlur: 20,
                        shadowColor: 'rgba(139, 92, 246, 0.6)'
                    }, // Purple
                    category: 0
                });
            }
            if (!uniqueNodes.has(event.child_district)) {
                uniqueNodes.add(event.child_district);
                nodes.push({
                    id: event.child_district,
                    name: event.child_district,
                    symbolSize: 35,
                    itemStyle: {
                        color: '#10B981',
                        borderColor: '#ffffff',
                        borderWidth: 3,
                        shadowBlur: 15,
                        shadowColor: 'rgba(16, 185, 129, 0.6)'
                    }, // Emerald
                    category: 1
                });
            }

            links.push({
                source: event.parent_district,
                target: event.child_district,
                label: {
                    show: true,
                    formatter: `${event.split_year}`,
                    fontSize: 10,
                    fontFamily: 'Inter, sans-serif',
                    fontWeight: 700,
                    color: '#64748b',
                    backgroundColor: '#ffffff',
                    padding: [3, 6],
                    borderRadius: 12,
                    borderWidth: 1,
                    borderColor: '#cbd5e1'
                },
                lineStyle: {
                    color: '#94a3b8',
                    width: 2.5,
                    curveness: 0.25,
                    type: 'solid',
                    opacity: 0.7
                }
            });
        });

        return { nodes, links };
    }, [history]);

    // Filter coverage by search
    const filteredCoverage = useMemo(() => {
        if (!coverage?.coverage) return [];
        if (!coverageSearch) return coverage.coverage;
        const q = coverageSearch.toLowerCase();
        return coverage.coverage.filter((d: { district_name: string }) =>
            d.district_name.toLowerCase().includes(q)
        );
    }, [coverage, coverageSearch]);

    return (
        <main className="page-container">
            {/* Header */}
            <div className="mb-8">
                <div className="flex items-center gap-3 mb-1">
                    <GitBranch className="text-purple-600" size={24} />
                    <h1 className="text-2xl font-bold text-slate-900">District Lineage Explorer</h1>
                </div>
                <p className="text-slate-500 text-sm font-medium">Explore administrative boundary changes and data provenance (1951–2024)</p>
            </div>

            {/* Context Banner */}
            <div className="mb-8 bg-purple-50 border border-purple-200 rounded-xl p-5">
                <h3 className="text-purple-800 font-bold mb-2 flex items-center gap-2 text-sm">
                    <Info size={16} className="text-purple-600" />
                    Why District Lineage Matters
                </h3>
                <p className="text-slate-600 text-sm leading-relaxed font-medium">
                    India&apos;s administrative map has been continuously redrawn since Independence. Over <strong className="text-purple-800">565 district split events</strong> have been documented across seven decades, with 64% concentrated after 1991. When datasets don&apos;t account for these evolving boundaries, apparent changes in agricultural yield often reflect statistical artifacts of spatial reconfiguration—not genuine agronomic shifts. This explorer lets you trace the exact lineage of these boundary changes.
                </p>
            </div>

            {/* State Selector */}
            <div className="mb-6 flex items-center gap-3">
                <select
                    value={selectedState}
                    onChange={(e) => setSelectedState(e.target.value)}
                    disabled={isLoadingStates || !states}
                    className="bg-white border border-slate-200 text-slate-900 rounded-lg px-4 py-2 text-sm focus:border-purple-500 transition min-w-[220px] shadow-sm disabled:bg-slate-50 disabled:text-slate-500"
                >
                    <option value="">{isLoadingStates ? 'Loading states... (Waking server)' : 'Select a state...'}</option>
                    {states?.map((s) => (
                        <option key={s.state} value={s.state}>{s.state}</option>
                    ))}
                </select>
                {isLoadingStates && <div className="text-xs text-purple-600 animate-pulse font-medium">Backend is waking up, please wait (~50s)...</div>}
                {!isLoadingStates && !states && <div className="text-xs text-rose-500 font-medium">Backend offline. Please refresh.</div>}
            </div>

            {/* Empty State */}
            {!selectedState && !hasErrors && (
                <div className="text-center py-24 px-4">
                    <div className="w-20 h-20 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-5">
                        <GitBranch className="text-slate-600" size={36} />
                    </div>
                    <h3 className="text-lg font-bold text-slate-700">No State Selected</h3>
                    <p className="text-slate-500 text-sm mt-1 max-w-md mx-auto">Select a state above to explore how its districts have evolved through splits and reorganizations.</p>
                </div>
            )}

            {/* Loading */}
            {(isLoadingHistory || isLoadingCoverage) && (
                <div className="flex flex-col items-center justify-center py-24">
                    <div className="w-10 h-10 border-2 border-purple-200 border-t-purple-600 rounded-full animate-spin mb-4" />
                    <p className="text-sm font-medium text-slate-500">Loading lineage data...</p>
                </div>
            )}

            {/* Error State */}
            {hasErrors && (
                <div className="bg-rose-50 border border-rose-200 rounded-xl p-8 text-center my-8">
                    <Activity className="mx-auto text-rose-500 mb-4" size={32} />
                    <h3 className="text-lg font-bold text-rose-800 mb-2">Failed to load data</h3>
                    <p className="text-sm text-rose-600 max-w-md mx-auto">There was an error communicating with the server. Please try refreshing the page or selecting a different state.</p>
                </div>
            )}

            {selectedState && history && !isLoadingHistory && !hasErrors && (
                <>
                    {/* ── Summary Stats ── */}
                    {summaryStats && (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6 animate-in">
                            <div className="stat-card text-center border-l-4 border-purple-500 py-3">
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-1 font-bold">Split Events</div>
                                <div className="text-2xl font-bold text-purple-600">{summaryStats.totalEvents}</div>
                            </div>
                            <div className="stat-card text-center border-l-4 border-cyan-500 py-3">
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-1 font-bold">Time Span</div>
                                <div className="text-lg font-bold text-cyan-600">{summaryStats.timeSpan}</div>
                            </div>
                            <div className="stat-card text-center border-l-4 border-amber-500 py-3">
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-1 font-bold">Parent Districts</div>
                                <div className="text-2xl font-bold text-amber-600">{summaryStats.uniqueParents}</div>
                            </div>
                            <div className="stat-card text-center border-l-4 border-emerald-500 py-3">
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-1 font-bold">Across Decades</div>
                                <div className="text-2xl font-bold text-emerald-600">{summaryStats.decadeCount}</div>
                            </div>
                        </div>
                    )}

                    {/* ── Main Content Grid ── */}
                    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 animate-in">
                        <div className="xl:col-span-2 space-y-4">
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-2">
                                <h3 className="section-header flex items-center gap-2 mb-0">
                                    <GitBranch size={16} className="text-purple-600" />
                                    Interactive Lineage Network
                                </h3>
                                {/* View Toggle */}
                                <div className="flex items-center bg-slate-100 rounded-lg p-1 border border-slate-200 self-start sm:self-auto">
                                    <button
                                        onClick={() => setViewMode('graph')}
                                        className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === 'graph' ? 'bg-white text-purple-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
                                    >
                                        <Activity size={14} /> Network
                                    </button>
                                    <button
                                        onClick={() => setViewMode('table')}
                                        className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === 'table' ? 'bg-white text-purple-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
                                        aria-label="View as data table"
                                    >
                                        <TableIcon size={14} /> Data Table
                                    </button>
                                </div>
                            </div>

                            {!graphData ? (
                                <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-8 text-center h-[500px] flex justify-center items-center flex-col">
                                    <GitBranch className="mx-auto text-slate-500 mb-3" size={32} />
                                    <p className="text-slate-500 text-sm font-medium">No split events recorded for {selectedState}</p>
                                    <p className="text-slate-600 text-xs mt-1">This state may not have undergone district reorganization</p>
                                </div>
                            ) : viewMode === 'graph' ? (
                                <div
                                    className="bg-slate-50 border border-slate-200 shadow-sm rounded-xl overflow-hidden h-[500px] md:h-[600px] relative"
                                    style={{
                                        backgroundImage: 'radial-gradient(#cbd5e1 1px, transparent 1px)',
                                        backgroundSize: '24px 24px'
                                    }}
                                    role="img"
                                    aria-label={`Interactive force-directed graph showing district splits for ${selectedState}`}
                                >
                                    <ReactECharts
                                        option={{
                                            tooltip: {
                                                trigger: 'item',
                                                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                                                borderColor: '#e2e8f0',
                                                borderWidth: 1,
                                                textStyle: { color: '#1e293b' },
                                                formatter: function (params: any /* eslint-disable-line @typescript-eslint/no-explicit-any */) {
                                                    if (params.dataType === 'node') {
                                                        return `<div class="font-bold text-sm mb-1">${params.data.name}</div><div class="text-xs text-gray-500 flex items-center gap-1">Click to view data coverage</div>`;
                                                    } else if (params.dataType === 'edge') {
                                                        return `<div class="font-semibold text-sm mb-1 text-slate-700">${params.data.source} <span style="color:#94a3b8">➔</span> ${params.data.target}</div><div class="text-xs text-gray-500">Split Occurred: <span class="font-mono font-bold text-purple-600">${params.data.label.formatter}</span></div>`;
                                                    }
                                                }
                                            },
                                            animationDurationUpdate: 1500,
                                            animationEasingUpdate: 'quinticInOut',
                                            series: [
                                                {
                                                    type: 'graph',
                                                    layout: 'force',
                                                    data: graphData.nodes,
                                                    links: graphData.links,
                                                    roam: true,
                                                    label: {
                                                        show: true,
                                                        position: 'right',
                                                        formatter: '{b}',
                                                        fontFamily: 'Inter, sans-serif',
                                                        fontWeight: 600,
                                                        color: '#1e293b',
                                                        backgroundColor: 'rgba(255, 255, 255, 0.85)',
                                                        padding: [4, 8],
                                                        borderRadius: 6,
                                                        borderWidth: 1,
                                                        borderColor: '#e2e8f0',
                                                        shadowBlur: 8,
                                                        shadowColor: 'rgba(0,0,0,0.05)'
                                                    },
                                                    force: {
                                                        repulsion: 1200,
                                                        edgeLength: [120, 180],
                                                        gravity: 0.1,
                                                        friction: 0.2
                                                    },
                                                    edgeSymbol: ['circle', 'arrow'],
                                                    edgeSymbolSize: [5, 10],
                                                    emphasis: {
                                                        focus: 'adjacency',
                                                        lineStyle: {
                                                            width: 4,
                                                            opacity: 1
                                                        },
                                                        itemStyle: {
                                                            shadowBlur: 30
                                                        }
                                                    }
                                                }
                                            ]
                                        }}
                                        style={{ height: '100%', width: '100%' }}
                                        onEvents={{
                                            'click': (params: any /* eslint-disable-line @typescript-eslint/no-explicit-any */) => {
                                                if (params.dataType === 'node') {
                                                    // Try to match the clicked node to a CDK from coverage lists
                                                    const matchedDistrict = coverage?.coverage?.find((d: any /* eslint-disable-line @typescript-eslint/no-explicit-any */) => d.district_name === params.data.name);
                                                    if (matchedDistrict) {
                                                        setSelectedCdk(matchedDistrict.cdk);
                                                        // Auto-scroll to sidebar on mobile
                                                        if (window.innerWidth < 1280) {
                                                            document.getElementById('sidebar-panel')?.scrollIntoView({ behavior: 'smooth' });
                                                        }
                                                    }
                                                }
                                            }
                                        }}
                                    />
                                    <div className="absolute bottom-4 left-4 bg-white/95 backdrop-blur-md px-4 py-3 rounded-xl border border-slate-200 shadow-md text-xs text-slate-600 flex flex-col gap-2 pointer-events-none transition-all hidden sm:flex">
                                        <div className="flex items-center gap-2 font-medium">
                                            <span className="w-3.5 h-3.5 rounded-full bg-purple-500 shadow-[0_0_10px_rgba(139,92,246,0.6)] border-2 border-white inline-block"></span>
                                            Parent District
                                        </div>
                                        <div className="flex items-center gap-2 font-medium">
                                            <span className="w-3.5 h-3.5 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.6)] border-2 border-white inline-block"></span>
                                            Child District (Created)
                                        </div>
                                        <div className="mt-1 pt-2 border-t border-slate-100 flex items-center gap-1.5 text-[10px] text-slate-400 font-medium tracking-wide uppercase">
                                            <Info size={12} /> Scroll to zoom, drag to pan
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <div className="bg-white border border-slate-200 shadow-sm rounded-xl overflow-hidden">
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-sm text-left">
                                            <thead className="text-xs text-slate-500 uppercase bg-slate-50 border-b border-slate-200">
                                                <tr>
                                                    <th className="px-6 py-4 font-bold tracking-wider">Split Year</th>
                                                    <th className="px-6 py-4 font-bold tracking-wider">Parent District</th>
                                                    <th className="px-6 py-4 font-bold tracking-wider">Child District Created</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {Object.entries(decades)
                                                    .sort(([a], [b]) => Number(a) - Number(b))
                                                    .map(([decade, events]) => (
                                                        <React.Fragment key={decade}>
                                                            <tr className="bg-slate-100/50 border-b border-slate-200">
                                                                <td colSpan={3} className="px-6 py-2 text-xs font-bold text-slate-500 uppercase">
                                                                    {decade}s
                                                                </td>
                                                            </tr>
                                                            {events.sort((a, b) => a.split_year - b.split_year).map((event, idx) => (
                                                                <tr key={`${event.parent_district}-${event.child_district}-${idx}`} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                                                                    <td className="px-6 py-3 font-medium text-slate-900">
                                                                        <span className="px-2.5 py-1 bg-white border border-slate-200 rounded-md shadow-sm text-slate-700">
                                                                            {event.split_year}
                                                                        </span>
                                                                    </td>
                                                                    <td className="px-6 py-3 text-purple-700 font-semibold flex items-center gap-2">
                                                                        <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                                                                        {event.parent_district}
                                                                    </td>
                                                                    <td className="px-6 py-3 text-emerald-700 font-semibold">
                                                                        <div className="flex items-center gap-2">
                                                                            <ArrowRight size={14} className="text-slate-400" />
                                                                            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                                                                            {event.child_district}
                                                                        </div>
                                                                    </td>
                                                                </tr>
                                                            ))}
                                                        </React.Fragment>
                                                    ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Right sidebar: Tracking + Coverage */}
                        <div id="sidebar-panel" className="space-y-6">
                            {/* Data Provenance */}
                            {tracking && tracking.district && (
                                <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-5 animate-in">
                                    <div className="flex items-center gap-2 mb-4">
                                        <Database size={14} className="text-cyan-600" />
                                        <h3 className="section-header mb-0">Data Provenance</h3>
                                    </div>
                                    <div className="space-y-3">
                                        <div>
                                            <div className="text-xs text-slate-500 font-bold uppercase tracking-wider">District</div>
                                            <div className="text-sm text-slate-900 font-semibold">{tracking.district.district_name}</div>
                                        </div>
                                        <div>
                                            <div className="text-xs text-slate-500 font-bold uppercase tracking-wider">State</div>
                                            <div className="text-sm text-slate-700">{tracking.district.state_name}</div>
                                        </div>
                                        <div className="grid grid-cols-2 gap-3">
                                            <div className="bg-slate-50 border border-slate-200 rounded-lg p-2">
                                                <div className="text-xs text-slate-500 font-bold">Years with Data</div>
                                                <div className="text-sm text-emerald-600 font-bold">{tracking.data_coverage.years_with_data}</div>
                                            </div>
                                            <div className="bg-slate-50 border border-slate-200 rounded-lg p-2">
                                                <div className="text-xs text-slate-500 font-bold">Total Records</div>
                                                <div className="text-sm text-emerald-600 font-bold">{tracking.data_coverage.total_records}</div>
                                            </div>
                                        </div>
                                        <div>
                                            <div className="text-xs text-slate-500 font-bold uppercase tracking-wider">Coverage</div>
                                            <div className="text-sm text-slate-700 font-medium">
                                                {tracking.data_coverage.first_year} – {tracking.data_coverage.last_year}
                                            </div>
                                        </div>
                                        {tracking.data_sources?.map((src: { source: string; record_count: number }, i: number) => (
                                            <div key={i} className="p-2 bg-slate-50 rounded-lg border border-slate-200">
                                                <div className="text-xs text-slate-600 font-semibold">{src.source}</div>
                                                <div className="text-xs text-slate-500">{src.record_count.toLocaleString()} records</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Coverage Table */}
                            {coverage && (
                                <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-5">
                                    <div className="flex items-center gap-2 mb-3">
                                        <MapPin size={14} className="text-emerald-600" />
                                        <h3 className="section-header mb-0">Coverage ({coverage.districts} districts)</h3>
                                    </div>

                                    {/* Search */}
                                    <div className="relative mb-3">
                                        <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-600" />
                                        <input
                                            type="text"
                                            value={coverageSearch}
                                            onChange={(e) => setCoverageSearch(e.target.value)}
                                            placeholder="Filter districts..."
                                            className="w-full bg-slate-50 border border-slate-200 rounded-md pl-7 pr-3 py-1.5 text-xs text-slate-900 placeholder:text-slate-600 focus:border-purple-500 outline-none transition"
                                        />
                                    </div>

                                    <div className="max-h-[400px] overflow-y-auto custom-scrollbar space-y-1">
                                        {filteredCoverage.map((d: { cdk: string; district_name: string; years_with_data: number; record_count: number }, i: number) => (
                                            <button
                                                key={i}
                                                onClick={() => setSelectedCdk(d.cdk)}
                                                className={`w-full flex items-center justify-between p-2 rounded text-left transition ${selectedCdk === d.cdk ? 'bg-purple-50 border border-purple-200' : 'hover:bg-slate-50 border border-transparent'
                                                    }`}
                                            >
                                                <span className="text-xs text-slate-700 truncate flex-1 font-medium">{d.district_name}</span>
                                                <span className={`text-[10px] ml-2 px-1.5 py-0.5 rounded-full font-bold ${d.years_with_data > 20 ? 'text-emerald-700 bg-emerald-50 border border-emerald-200' :
                                                    d.years_with_data > 0 ? 'text-amber-700 bg-amber-50 border border-amber-200' :
                                                        'text-slate-500 bg-slate-100 border border-slate-200'
                                                    }`}>
                                                    {d.years_with_data}y
                                                </span>
                                            </button>
                                        ))}
                                        {filteredCoverage.length === 0 && (
                                            <p className="text-xs text-slate-600 text-center py-4">No matching districts</p>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </>
            )}
        </main>
    );
}
