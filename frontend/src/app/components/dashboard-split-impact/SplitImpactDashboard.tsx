
"use client";

import React, { useState, useEffect, useMemo } from 'react';
import { StateSummaryPanel } from './StateSummaryPanel';
import SplitDistrictTable from './SplitDistrictTable';
import { ComparisonView } from './ComparisonView';
import { ComparisonModeSelector } from './ComparisonModeSelector';
import { LayoutDashboard, ChevronLeft, Menu, X } from 'lucide-react';

import { useSplitEvents } from '../../hooks/useSplitImpact';
import { useQuery } from '@tanstack/react-query'; // Assuming this import is needed for useQuery
import { api } from '../../services/api';
import { AnalysisMode, SplitDistrict, StateSummary } from '../../services/api';

export function SplitImpactDashboard() {
    // New React Query Hooks
    const { data: summaryData, isLoading: isLoadingSummary } = useQuery({ queryKey: ['stateSummary'], queryFn: api.getSummary, staleTime: 3600000 });
    const [selectedState, setSelectedState] = useState('');
    const { data: splitEventsData, isLoading: splitEventsLoading } = useSplitEvents(selectedState);

    // Derived state from query data
    const states = useMemo(() => {
        if (!summaryData?.states) return [];
        if (Array.isArray(summaryData.states)) return summaryData.states;
        return Object.keys(summaryData.states).sort();
    }, [summaryData]);
    const allStats: StateSummary['stats'] = summaryData?.stats || {};
    const splitEvents = splitEventsData || [];

    // Selectors
    const [selectedCrop, setSelectedCrop] = useState('wheat');
    const [selectedMetric, setSelectedMetric] = useState('yield');

    // Selection
    const [selectedEvent, setSelectedEvent] = useState<SplitDistrict | null>(null);
    const [comparisonMode, setComparisonMode] = useState<AnalysisMode>('before_after');

    // Mobile UI state
    const [showMobileMenu, setShowMobileMenu] = useState(false);
    const [mobileView, setMobileView] = useState<'list' | 'analysis'>('list');

    // Helper: Smart Default for Crop based on Region
    const getDefaultCrop = (stateName: string) => {
        const s = stateName.toLowerCase();
        // Wheat Belt
        const wheatStates = ['punjab', 'haryana', 'uttar pradesh', 'madhya pradesh', 'rajasthan', 'bihar', 'gujarat', 'himachal', 'uttarakhand'];
        if (wheatStates.some(w => s.includes(w))) return 'wheat';
        // Default to Rice (South, East, Islands)
        return 'rice';
    };

    // Initial Load of States - Set Default State
    // Initial Load of States - Set Default State
    useEffect(() => {
        if (states.length > 0 && !selectedState) {
            const firstState = states[0];
            setSelectedState(firstState);
            setSelectedCrop(getDefaultCrop(firstState));
        }
        // Initialize only once when states load
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [states]);

    const currentStateStats = allStats[selectedState] || null;

    const handleEventSelect = (event: SplitDistrict) => {
        setSelectedEvent(event);
        // Auto-switch to analysis view on mobile
        if (window.innerWidth < 1024) {
            setMobileView('analysis');
        }
    };

    return (
        <div className="w-full text-slate-900 p-4 md:p-6 lg:p-8 font-sans selection:bg-indigo-500/30">
            {/* Header */}
            <div className="flex flex-col gap-4 mb-6 border-b border-slate-200 pb-4 md:pb-6">
                {/* Title Row */}
                <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                        <h1 className="text-xl md:text-2xl lg:text-3xl font-bold text-slate-900 flex items-center gap-2 md:gap-3 truncate tracking-tight">
                            <LayoutDashboard className="text-indigo-600 shrink-0 w-5 h-5 md:w-6 md:h-6" />
                            <span className="hidden sm:inline">Boundary Split Impact Analysis</span>
                            <span className="sm:hidden">Split Impact</span>
                        </h1>
                        <p className="text-slate-600 mt-1 md:mt-2 text-xs md:text-sm leading-relaxed hidden md:block max-w-2xl font-medium">
                            Scientific analysis of agricultural performance across district boundary changes.
                        </p>
                    </div>

                    {/* Mobile Menu Toggle */}
                    <button
                        className="lg:hidden p-2 rounded-lg bg-white border border-slate-300 text-slate-600 hover:bg-slate-50 transition"
                        onClick={() => setShowMobileMenu(!showMobileMenu)}
                    >
                        {showMobileMenu ? <X size={20} /> : <Menu size={20} />}
                    </button>
                </div>

                {/* Controls - Always visible on desktop, toggle on mobile */}
                <div className={`${showMobileMenu ? 'flex' : 'hidden'} lg:flex flex-wrap gap-2 md:gap-3 bg-white p-2 md:p-3 rounded-xl border border-slate-200 shadow-sm`}>
                    {/* State Selector */}
                    <div className="flex flex-col gap-1 flex-1 min-w-[120px]">
                        <label className="text-[10px] uppercase font-bold text-slate-500 px-1">State</label>
                        <select
                            value={selectedState}
                            onChange={e => {
                                const s = e.target.value;
                                setSelectedState(s);
                                setSelectedCrop(getDefaultCrop(s));
                                setSelectedEvent(null);
                                setMobileView('list');
                            }}
                            className="bg-slate-50 border border-slate-300 rounded-lg px-2 md:px-3 py-1.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none text-slate-900 w-full transition shadow-sm"
                            disabled={isLoadingSummary}
                        >
                            <option value="" className="text-slate-900">Select state...</option>
                            {states.map((s) => <option key={s as string} value={s as string} className="text-slate-900">{s as string}</option>)}
                        </select>
                    </div>

                    {/* Crop Selector */}
                    <div className="flex flex-col gap-1 flex-1 min-w-[100px]">
                        <label className="text-[10px] uppercase font-bold text-slate-500 px-1">Crop</label>
                        <select
                            value={selectedCrop}
                            onChange={e => setSelectedCrop(e.target.value)}
                            className="bg-slate-50 border border-slate-300 rounded-lg px-2 md:px-3 py-1.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none text-slate-900 w-full transition shadow-sm"
                        >
                            <option value="wheat">Wheat</option>
                            <option value="rice">Rice</option>
                            <option value="maize">Maize</option>
                            <option value="sorghum">Sorghum</option>
                            <option value="groundnut">Groundnut</option>
                            <option value="cotton">Cotton</option>
                            <option value="sugarcane">Sugarcane</option>
                        </select>
                    </div>

                    {/* Metric Selector */}
                    <div className="flex flex-col gap-1 flex-1 min-w-[100px]">
                        <label className="text-[10px] uppercase font-bold text-slate-500 px-1">Metric</label>
                        <select
                            value={selectedMetric}
                            onChange={e => setSelectedMetric(e.target.value)}
                            className="bg-slate-50 border border-slate-300 rounded-lg px-2 md:px-3 py-1.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none text-slate-900 w-full transition shadow-sm"
                        >
                            <option value="yield">Yield (Kg/Ha)</option>
                            <option value="area">Area</option>
                            <option value="production">Production</option>
                        </select>
                    </div>
                </div>
            </div>

            {/* Summary - Scrollable on mobile */}
            <div className="overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0 mb-6">
                <StateSummaryPanel stateName={selectedState} stats={currentStateStats} />
            </div>

            {/* Mobile View Toggle */}
            <div className="lg:hidden flex gap-2 mb-4">
                <button
                    onClick={() => setMobileView('list')}
                    className={`flex-1 py-2 px-4 rounded-lg text-sm font-semibold transition-colors ${mobileView === 'list'
                        ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                        : 'bg-white text-slate-600 border border-slate-200'
                        }`}
                >
                    Split Events
                </button>
                <button
                    onClick={() => setMobileView('analysis')}
                    className={`flex-1 py-2 px-4 rounded-lg text-sm font-semibold transition-colors ${mobileView === 'analysis'
                        ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                        : 'bg-white text-slate-600 border border-slate-200'
                        }`}
                    disabled={!selectedEvent}
                >
                    Analysis {selectedEvent ? '✓' : ''}
                </button>
            </div>

            {/* Main Content */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 md:gap-6 lg:gap-8">
                {/* Table (Left) - Hidden on mobile when viewing analysis */}
                <div className={`lg:col-span-5 flex flex-col gap-4 ${mobileView === 'analysis' ? 'hidden lg:flex' : 'flex'}`}>
                    <div className="max-h-[50vh] lg:max-h-[calc(100vh-350px)] overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent pr-2">
                        <SplitDistrictTable
                            splits={splitEvents}
                            onSelect={handleEventSelect}
                            selectedEventId={selectedEvent?.id}
                            isLoading={splitEventsLoading}
                        />
                    </div>
                </div>

                {/* Charts (Right) - Full width on mobile when viewing analysis */}
                <div className={`lg:col-span-7 flex flex-col min-h-[60vh] lg:min-h-[600px] lg:h-[calc(100vh-350px)] overflow-y-auto scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-transparent ${mobileView === 'list' ? 'hidden lg:flex' : 'flex'}`}>
                    {selectedEvent ? (
                        <>
                            {/* Back button on mobile */}
                            <button
                                className="lg:hidden flex items-center gap-2 text-slate-500 hover:text-slate-900 mb-3 text-sm font-medium transition"
                                onClick={() => setMobileView('list')}
                            >
                                <ChevronLeft size={16} />
                                Back to Split Events
                            </button>

                            <ComparisonModeSelector mode={comparisonMode} onChange={setComparisonMode} />
                            <ComparisonView
                                event={selectedEvent}
                                crop={selectedCrop}
                                metric={selectedMetric}
                                mode={comparisonMode}
                            />
                        </>
                    ) : (
                        <div className="h-full border border-dashed border-slate-300 rounded-xl flex flex-col items-center justify-center text-slate-500 bg-white shadow-sm p-6">
                            <LayoutDashboard size={48} className="mb-4 opacity-70 text-indigo-400" />
                            <p className="text-lg font-semibold text-slate-700 text-center tracking-tight">Select a split event</p>
                            <p className="text-sm text-slate-500 text-center mt-1">Choose a district from the list to begin analysis.</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
