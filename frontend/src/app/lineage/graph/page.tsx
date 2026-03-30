'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
    ReactFlow,
    Controls,
    Background,
    MiniMap,
    Panel,
    Node,
    Edge,
    Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import { api } from '../../services/api';
import { AlertTriangle, GitBranch, Database, MapPin, Search } from 'lucide-react';

import { LineageCoverageItem, SplitEvent } from '../../services/api/types';
// Dagre topological layout engine
const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'LR') => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    
    // For tighter horizontal layout, use RankDir=LR (Left to Right)
    const nodeWidth = 180;
    const nodeHeight = 50;
    
    dagreGraph.setGraph({ rankdir: direction, ranksep: 80, nodesep: 40 });

    nodes.forEach((node) => {
        dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
    });

    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    nodes.forEach((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        node.targetPosition = direction === 'LR' ? Position.Left : Position.Top;
        node.sourcePosition = direction === 'LR' ? Position.Right : Position.Bottom;
        node.position = {
            x: nodeWithPosition.x - nodeWidth / 2,
            y: nodeWithPosition.y - nodeHeight / 2,
        };
        return node;
    });

    return { nodes, edges };
};

export default function LineagePage() {
    const [selectedState, setSelectedState] = useState<string>('');
    const [selectedCdk, setSelectedCdk] = useState<string>('');
    const [coverageSearch, setCoverageSearch] = useState('');
    const [viewMode, setViewMode] = useState<'graph' | 'table'>('graph');

    const { data: states, isLoading: isLoadingStates, isError: isStatesError } = useQuery({
        queryKey: ['states-list'],
        queryFn: () => api.getStatesList(),
    });

    const { data: history, isError: isHistoryError } = useQuery({
        queryKey: ['lineage-history', selectedState],
        queryFn: () => api.getLineageHistory(selectedState),
        enabled: !!selectedState,
    });

    const { data: tracking } = useQuery({
        queryKey: ['lineage-tracking', selectedCdk],
        queryFn: () => api.getDataTracking(selectedCdk),
        enabled: !!selectedCdk,
    });

    const { data: coverage, isError: isCoverageError } = useQuery({
        queryKey: ['state-coverage', selectedState],
        queryFn: () => api.getStateCoverage(selectedState),
        enabled: !!selectedState,
    });

    const hasFatalErrors = isStatesError || isHistoryError;
    const hasCoverageWarning = isCoverageError && !hasFatalErrors;

    // Reset selectedCdk and coverageSearch when state changes
    useEffect(() => {
        setSelectedCdk('');
        setCoverageSearch('');
    }, [selectedState]);

    // Construct React Flow Graph Data using Dagre Layout
    const { nodes: flowNodes, edges: flowEdges } = useMemo(() => {
        if (!history || history.length === 0) return { nodes: [], edges: [] };

        const initialNodes: Node[] = [];
        const initialEdges: Edge[] = [];
        const uniqueNodes = new Set<string>();

        history.forEach((event: SplitEvent) => {
            if (!uniqueNodes.has(event.parent_district)) {
                uniqueNodes.add(event.parent_district);
                initialNodes.push({
                    id: event.parent_district,
                    data: { label: event.parent_district },
                    position: { x: 0, y: 0 },
                    type: 'default',
                    style: {
                        background: '#f8fafc',
                        border: '2px solid #8B5CF6',
                        borderRadius: '8px',
                        fontWeight: 600,
                        color: '#334155',
                        boxShadow: '0 4px 6px -1px rgba(139, 92, 246, 0.1)',
                        padding: '10px 15px',
                        minWidth: '150px'
                    }
                });
            }
            if (!uniqueNodes.has(event.child_district)) {
                uniqueNodes.add(event.child_district);
                initialNodes.push({
                    id: event.child_district,
                    data: { label: event.child_district },
                    position: { x: 0, y: 0 },
                    style: {
                        background: '#ffffff',
                        border: '2px solid #10B981',
                        borderRadius: '8px',
                        fontWeight: 600,
                        color: '#334155',
                        boxShadow: '0 4px 6px -1px rgba(16, 185, 129, 0.1)',
                        padding: '10px 15px',
                        minWidth: '150px'
                    }
                });
            }

            initialEdges.push({
                id: `e-${event.parent_district}-${event.child_district}`,
                source: event.parent_district,
                target: event.child_district,
                label: String(event.split_year),
                animated: true,
                style: { stroke: '#94a3b8', strokeWidth: 2 },
                labelStyle: { fill: '#475569', fontWeight: 700, fontSize: 12 },
                labelBgStyle: { fill: '#f8fafc', fillOpacity: 0.9, rx: 4, ry: 4 },
                labelBgPadding: [6, 4]
            });
        });

        // Apply automatic topological layout
        return getLayoutedElements(initialNodes, initialEdges, 'LR');
    }, [history]);

    // Handle Node Click
    const onNodeClick = (event: React.MouseEvent, node: Node) => {
        const matchedDistrict = coverage?.coverage?.find((d: LineageCoverageItem) => d.district_name === node.data.label);
        if (matchedDistrict) {
            setSelectedCdk(matchedDistrict.cdk);
            if (window.innerWidth < 1280) {
                document.getElementById('sidebar-panel')?.scrollIntoView({ behavior: 'smooth' });
            }
        }
    };

    return (
        <main className="page-container h-screen flex flex-col">
            {/* Header */}
            <div className="mb-6 flex-shrink-0">
                <div className="flex items-center gap-3 mb-1">
                    <GitBranch className="text-purple-600" size={24} />
                    <h1 className="text-2xl font-bold text-slate-900">District Lineage Constructor V2</h1>
                </div>
                <p className="text-slate-500 text-sm font-medium">Fully interactive DAG visualizer powered by React Flow</p>
            </div>

            <div className="flex gap-4 mb-4 flex-shrink-0">
                {/* State Selector */}
                <select
                    value={selectedState}
                    onChange={(e) => setSelectedState(e.target.value)}
                    disabled={isLoadingStates || !states}
                    className="bg-white border border-slate-200 text-slate-900 rounded-lg px-4 py-2 text-sm focus:border-purple-500 transition min-w-[220px] shadow-sm"
                >
                    <option value="">{isLoadingStates ? 'Loading states...' : 'Select a state...'}</option>
                    {states?.map((s: {state: string}) => (
                        <option key={s.state} value={s.state}>{s.state}</option>
                    ))}
                </select>
                
                {/* View toggles */}
                 <div className="flex items-center bg-slate-100 rounded-lg p-1 border border-slate-200">
                    <button
                        onClick={() => setViewMode('graph')}
                        className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === 'graph' ? 'bg-white text-purple-700 shadow-sm' : 'text-slate-600'}`}
                    >
                        Interactive DAG
                    </button>
                    <button
                        onClick={() => setViewMode('table')}
                        className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === 'table' ? 'bg-white text-purple-700 shadow-sm' : 'text-slate-600'}`}
                    >
                        Raw Split Logs
                    </button>
                </div>
            </div>

            {/* Empty States */}
            {!selectedState && !hasFatalErrors && (
                <div className="bg-slate-50 rounded-xl flex-grow flex items-center justify-center border border-dashed border-slate-300">
                    <div className="text-center">
                        <GitBranch className="text-slate-400 mx-auto mb-3" size={40} />
                        <h3 className="text-lg font-bold text-slate-700">Select a State to View Graph</h3>
                    </div>
                </div>
            )}

            {hasFatalErrors && (
                <div className="bg-rose-50 rounded-xl flex-grow flex items-center justify-center border border-rose-200">
                    <div className="text-center text-rose-600 font-bold">Failed to load data from server.</div>
                </div>
            )}

            {/* Main Interactive Graph View */}
            {selectedState && history && viewMode === 'graph' && (
                <div className="flex-grow flex flex-col xl:flex-row gap-6 h-[500px] overflow-hidden">
                    {/* Left: React Flow Graph */}
                    <div className="flex-grow bg-slate-50 border border-slate-200 shadow-sm rounded-xl overflow-hidden relative">
                        <ReactFlow
                            nodes={flowNodes}
                            edges={flowEdges}
                            onNodeClick={onNodeClick}
                            fitView
                            fitViewOptions={{ padding: 0.2 }}
                            minZoom={0.2}
                            attributionPosition="bottom-right"
                        >
                            <Background color="#cbd5e1" gap={24} />
                            <Controls className="bg-white border-slate-200" />
                            <MiniMap nodeStrokeColor="#e2e8f0" nodeColor="#f1f5f9" maskColor="rgba(255,255,255,0.7)" />
                            <Panel position="top-left" className="bg-white/90 backdrop-blur p-3 rounded-lg border border-slate-200 shadow-sm text-xs font-medium">
                                <div className="flex items-center gap-2 mb-1">
                                    <div className="w-3 h-3 rounded bg-[#f8fafc] border-2 border-purple-500"></div> Parent District
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="w-3 h-3 rounded bg-white border-2 border-emerald-500"></div> Child District
                                </div>
                                <div className="mt-2 text-[10px] text-slate-400">Click a node to view its provenance data.</div>
                            </Panel>
                        </ReactFlow>
                    </div>

                    {/* Right: Tracket Sidebar */}
                    <div id="sidebar-panel" className="w-full xl:w-[350px] shrink-0 h-full overflow-y-auto space-y-4 pb-10 custom-scrollbar">
                        {hasCoverageWarning && (
                            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
                                <div className="flex items-start gap-2">
                                    <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                                    <div>
                                        Coverage metadata could not be loaded for {selectedState}. The lineage graph is still available, but node-to-dataset tracking may be incomplete.
                                    </div>
                                </div>
                            </div>
                        )}
                        {tracking && tracking.district ? (
                            <div className="bg-white border text-sm border-slate-200 shadow-sm rounded-xl p-5">
                                <div className="flex items-center gap-2 mb-4">
                                    <Database size={16} className="text-cyan-600" />
                                    <h3 className="font-bold text-slate-800">Node Data Provenance</h3>
                                </div>
                                <div className="mb-3">
                                    <div className="text-xs text-slate-500 font-bold uppercase">Selected Node</div>
                                    <div className="text-lg text-purple-700 font-black">{tracking.district.district_name}</div>
                                </div>
                                <div className="grid grid-cols-2 gap-3 mb-4">
                                    <div className="bg-slate-50 border border-slate-200 rounded-lg p-2.5">
                                        <div className="text-xs text-slate-500 font-bold mb-1">Years active</div>
                                        <div className="text-xl text-emerald-600 font-black">{tracking.data_coverage.years_with_data}</div>
                                    </div>
                                    <div className="bg-slate-50 border border-slate-200 rounded-lg p-2.5">
                                        <div className="text-xs text-slate-500 font-bold mb-1">Metric records</div>
                                        <div className="text-xl text-emerald-600 font-black">{tracking.data_coverage.total_records}</div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="bg-white border text-sm border-slate-200 border-dashed shadow-sm rounded-xl p-8 text-center text-slate-500">
                                Click any node in the DAG to reveal its historical data coverage and metric sources.
                            </div>
                        )}
                        
                        {/* Coverage State Search List */}
                        {coverage && coverage.coverage && (
                             <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-4">
                                <div className="flex items-center gap-2 mb-3">
                                    <MapPin size={14} className="text-emerald-600" />
                                    <h3 className="font-bold text-slate-800 text-sm mb-0">Full Directory ({coverage.districts})</h3>
                                </div>
                                <div className="relative mb-3">
                                    <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-600" />
                                    <input
                                        type="text"
                                        value={coverageSearch}
                                        onChange={(e) => setCoverageSearch(e.target.value)}
                                        placeholder="Filter nodes..."
                                        className="w-full bg-slate-50 border border-slate-200 rounded-md pl-7 pr-3 py-1.5 text-xs text-slate-900 outline-none"
                                    />
                                </div>
                                <div className="max-h-[300px] overflow-y-auto custom-scrollbar space-y-1 pr-1">
                                    {coverage.coverage
                                        .filter((d: LineageCoverageItem) => !coverageSearch || d.district_name.toLowerCase().includes(coverageSearch.toLowerCase()))
                                        .map((d: LineageCoverageItem, i: number) => (
                                        <button
                                            key={i}
                                            onClick={() => setSelectedCdk(d.cdk)}
                                            className={`w-full flex items-center justify-between p-2 rounded text-left transition ${selectedCdk === d.cdk ? 'bg-purple-50 border border-purple-200' : 'hover:bg-slate-50 border border-transparent'}`}
                                        >
                                            <span className="text-xs text-slate-700 truncate font-medium">{d.district_name}</span>
                                            <span className="text-[10px] ml-2 font-bold text-slate-500">{d.years_with_data}y</span>
                                        </button>
                                    ))}
                                </div>
                             </div>
                        )}
                    </div>
                </div>
            )}

            {selectedState && history && viewMode === 'table' && (
                <div className="bg-white border border-slate-200 shadow-sm rounded-xl overflow-hidden flex-grow">
                    <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
                        <div>
                            <h2 className="text-sm font-bold text-slate-900">Raw Split Logs</h2>
                            <p className="text-xs text-slate-500 mt-1">
                                {history.length} split record{history.length === 1 ? '' : 's'} for {selectedState}
                            </p>
                        </div>
                    </div>

                    {history.length === 0 ? (
                        <div className="p-10 text-center text-slate-500 text-sm">
                            No split records were returned for {selectedState}.
                        </div>
                    ) : (
                        <div className="overflow-auto h-full max-h-[520px]">
                            <table className="w-full text-left text-sm">
                                <thead className="sticky top-0 bg-slate-50 border-b border-slate-200 z-10">
                                    <tr className="text-xs uppercase tracking-wide text-slate-500">
                                        <th className="px-4 py-3 font-semibold">Year</th>
                                        <th className="px-4 py-3 font-semibold">Parent</th>
                                        <th className="px-4 py-3 font-semibold">Child</th>
                                        <th className="px-4 py-3 font-semibold">Source</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {history.map((event: SplitEvent) => (
                                        <tr key={`${event.parent_district}-${event.child_district}-${event.split_year}`} className="hover:bg-slate-50">
                                            <td className="px-4 py-3 text-slate-700 font-medium">{event.split_year}</td>
                                            <td className="px-4 py-3 text-slate-800">{event.parent_district}</td>
                                            <td className="px-4 py-3 text-slate-800">{event.child_district}</td>
                                            <td className="px-4 py-3 text-slate-500">{event.source}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}
        </main>
    );
}
