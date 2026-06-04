"use client";

import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';
import { Search, MapPin, Calendar, Activity, Menu, X, ChevronDown } from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import Link from 'next/link';
import bridgeData from '../../data/map_bridge.json';
import AnalyticsPanel from './AnalyticsPanel';
import BookmarkPanel from './BookmarkPanel';

interface DashboardProps {
    selectedDistrict: string | null;
    selectedState?: string | null;
    currentYear: number;
    onClose: () => void;
    onDistrictSelect: (selection: { district: string, state: string }) => void;
    // New Props for Data Control
    currentCrop: string;
    onCropChange: (c: string) => void;
    currentMetric: string;
    onMetricChange: (m: string) => void;
    currentMode: string;
    onModeChange: (md: string) => void;
    districtData?: { value: number };
    // Rainfall Layer
    showRainfallLayer?: boolean;
    onRainfallLayerToggle?: () => void;
    onContextChange?: (context: { district: string; year: number; crop: string }) => void;
}

const CROPS = [
    { value: 'wheat', label: 'Wheat' },
    { value: 'rice', label: 'Rice' },
    { value: 'maize', label: 'Maize' },
    { value: 'sorghum', label: 'Sorghum' },
    { value: 'pearl_millet', label: 'Pearl Millet' },
    { value: 'finger_millet', label: 'Finger Millet' },
    { value: 'barley', label: 'Barley' },
    { value: 'chickpea', label: 'Chickpea' },
    { value: 'pigeonpea', label: 'Pigeonpea' },
    { value: 'groundnut', label: 'Groundnut' },
    { value: 'soyabean', label: 'Soyabean' },
    { value: 'sesamum', label: 'Sesamum' },
    { value: 'rapeseed_and_mustard', label: 'Rapeseed & Mustard' },
    { value: 'sunflower', label: 'Sunflower' },
    { value: 'sugarcane', label: 'Sugarcane' },
    { value: 'cotton', label: 'Cotton' },
    { value: 'oilseeds', label: 'Total Oilseeds' },
];

const Dashboard: React.FC<DashboardProps> = ({
    selectedDistrict,
    selectedState,
    // ...
    currentYear,
    onClose,
    onDistrictSelect,
    currentCrop,
    onCropChange,
    currentMetric,
    onMetricChange,
    currentMode,
    onModeChange,
    districtData,
    showRainfallLayer,
    onRainfallLayerToggle,
    onContextChange,
}) => {
    const [searchTerm, setSearchTerm] = useState('');
    const [searchResults, setSearchResults] = useState<{district: string, state: string}[]>([]);
    const [isMobileOpen, setIsMobileOpen] = useState(false);





    // Load available districts from Import
    const availableDistricts = React.useMemo(() => {
        const raw = bridgeData as Record<string, string>;
        const dists = Object.keys(raw).map(k => {
            const parts = k.split('|');
            return { district: parts[0], state: parts[1] };
        });
        const unique = new Map<string, {district: string, state: string}>();
        dists.forEach(d => unique.set(`${d.district}|${d.state}`, d));
        return Array.from(unique.values()).sort((a, b) => a.district.localeCompare(b.district));
    }, []);

    // History State
    // --- Refactored to React Query ---

    // 1. Resolve State Name first (needed for both History and Rainfall)
    const stateName = React.useMemo(() => {
        if (!selectedDistrict) return '';
        if (selectedState) return selectedState;
        
        // Fallback to bridgeData if not provided
        const raw = bridgeData as Record<string, string>;
        const stateKey = Object.keys(raw).find(k => k.startsWith(selectedDistrict + '|'));
        return stateKey ? stateKey.split('|')[1] : '';
    }, [selectedDistrict, selectedState]);

    // 2. History Query
    const { data: history = [] } = useQuery({
        queryKey: ['history', selectedDistrict, stateName, currentCrop],
        queryFn: () => api.getHistory(selectedDistrict!, currentCrop, stateName),
        enabled: !!selectedDistrict
    });

    // 3. Rainfall Query
    const { data: rainfallData, isLoading: rainfallLoading } = useQuery({
        queryKey: ['rainfall', selectedDistrict, stateName, currentYear],
        queryFn: () => api.getRainfall(selectedDistrict!, stateName, currentYear),
        enabled: !!selectedDistrict && !!stateName && showRainfallLayer
    });

    // Real Search Logic
    useEffect(() => {
        const timer = setTimeout(() => {
            if (searchTerm.length > 2) {
                const filtered = availableDistricts.filter(d =>
                    d.district.toLowerCase().includes(searchTerm.toLowerCase()) ||
                    d.state.toLowerCase().includes(searchTerm.toLowerCase())
                ).slice(0, 10);
                setSearchResults(filtered);
            } else {
                setSearchResults([]);
            }
        }, 300);

        return () => clearTimeout(timer);
    }, [searchTerm, availableDistricts]);


    // Full Sidebar Layout
    return (
        <>
            {/* Mobile Menu Toggle Button */}
            <button
                onClick={() => setIsMobileOpen(!isMobileOpen)}
                className="fixed top-4 left-4 z-[60] md:hidden bg-slate-900 border border-slate-700 p-2 rounded-lg shadow-lg"
                aria-label={isMobileOpen ? "Close menu" : "Open menu"}
            >
                {isMobileOpen ? (
                    <X size={24} className="text-emerald-400" />
                ) : (
                    <Menu size={24} className="text-emerald-400" />
                )}
            </button>

            {/* Backdrop for mobile */}
            {isMobileOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-40 md:hidden"
                    onClick={() => setIsMobileOpen(false)}
                />
            )}

            {/* Sidebar */}
            <div className={`
                fixed top-0 left-0 h-full w-80 max-w-[85vw] bg-slate-950 border-r border-slate-800 z-50 shadow-2xl flex flex-col
                transform transition-transform duration-300 ease-in-out
                ${isMobileOpen ? 'translate-x-0' : '-translate-x-full'}
                md:translate-x-0
            `}>
                {/* Header / Branding */}
                <div className="p-6 border-b border-slate-800 bg-slate-900/50">
                    <h1 className="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-teal-500 bg-clip-text text-transparent font-serif tracking-tight">
                        I-ASCAP
                    </h1>
                    <p className="text-[10px] text-slate-500 mt-2 uppercase tracking-[0.2em] font-medium leading-relaxed">
                        Indian Agri-Spatial<br />Comparative Analytics
                    </p>
                </div>

                {/* Search Section */}
                <div className="p-4 border-b border-slate-800 relative z-20">
                    <div className="relative">
                        <Search className="absolute left-3 top-2.5 text-slate-500" size={16} />
                        <input
                            type="text"
                            placeholder="Search district..."
                            className="w-full bg-slate-900 border border-slate-800 text-slate-200 rounded-md py-2 pl-9 pr-3 text-sm focus:border-emerald-500 outline-none transition-colors"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            aria-label="Search district"
                        />
                    </div>
                    {/* Search Results Dropdown */}
                    {searchResults.length > 0 && (
                        <ul className="absolute top-full left-4 right-4 mt-2 bg-slate-900 border border-slate-700 rounded-lg shadow-xl max-h-48 overflow-y-auto z-30 list-none p-0" role="listbox" aria-label="Search Results">
                            {searchResults.map((result, idx) => (
                                <li
                                    key={`${result.district}|${result.state}`}
                                    className="w-full text-left p-2.5 hover:bg-slate-800 text-slate-300 cursor-pointer flex flex-col gap-0.5 text-sm border-b border-slate-800 last:border-0"
                                    onClick={() => {
                                        onDistrictSelect(result);
                                        setSearchTerm('');
                                        setSearchResults([]);
                                    }}
                                >
                                    <div className="flex items-center gap-2">
                                        <MapPin size={14} className="text-emerald-500" />
                                        <span className="font-medium text-white">{result.district}</span>
                                    </div>
                                    <span className="text-[10px] text-slate-500 ml-6 uppercase">{result.state}</span>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>

                {/* Scrollable Content */}
                <div className="flex-1 overflow-y-auto p-4 space-y-6 scrollbar-thin scrollbar-thumb-slate-800">

                    {/* 0. Saved Views (New) */}
                    <BookmarkPanel
                        onSelect={(b) => {
                            if (onContextChange) {
                                onContextChange({
                                    district: b.district,
                                    year: b.year,
                                    crop: b.crop
                                });
                            } else {
                                onDistrictSelect({ district: b.district, state: b.state });
                                onCropChange(b.crop);
                            }
                        }}
                    />

                    {/* 1. Data Controls (Always Visible) */}
                    <div className="space-y-4">
                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                            <Activity size={12} className="text-emerald-500" /> Variables
                        </h3>

                        <div className="space-y-3">
                            <div>
                                <label htmlFor="crop-select" className="text-[10px] text-slate-500 uppercase font-bold block mb-1">Crop Type</label>
                                <select
                                    id="crop-select"
                                    value={currentCrop}
                                    onChange={(e) => onCropChange(e.target.value)}
                                    className="w-full bg-slate-900 border border-slate-800 text-slate-300 rounded focus:border-emerald-500 outline-none text-sm p-2"
                                >
                                    {CROPS.map(c => (
                                        <option key={c.value} value={c.value}>{c.label}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label htmlFor="metric-select" className="text-[10px] text-slate-500 uppercase font-bold block mb-1">Metric</label>
                                <select
                                    id="metric-select"
                                    value={currentMetric}
                                    onChange={(e) => onMetricChange(e.target.value)}
                                    className="w-full bg-slate-900 border border-slate-800 text-slate-300 rounded focus:border-emerald-500 outline-none text-sm p-2"
                                >
                                    <option value="yield">Yield (kg/ha)</option>
                                    <option value="production">Production (Tons)</option>
                                    <option value="area">Area (1000 ha)</option>
                                </select>
                            </div>
                            
                            <div className="flex flex-col">
                                <label htmlFor="mode-select" className="text-[10px] text-slate-500 uppercase font-bold block mb-1">Map Mode</label>
                                <select
                                    id="mode-select"
                                    value={currentMode}
                                    onChange={(e) => onModeChange(e.target.value)}
                                    className="bg-slate-900 border border-slate-700 text-white text-sm rounded-lg focus:ring-emerald-500 focus:border-emerald-500 block w-full p-2 appearance-none cursor-pointer"
                                >
                                    <option value="historical">Historical System (1966)</option>
                                    <option value="modern">Modern System (Current)</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    {/* Modules */}
                    <div className="pt-2 space-y-2">
                        <Link
                            href="/dashboard/split-impact"
                            className="flex items-center justify-between p-3 rounded-lg bg-slate-900/50 border border-slate-800 hover:border-emerald-500/50 hover:bg-slate-800 transition-all group"
                        >
                            <div className="flex items-center gap-3">
                                <div className="p-1.5 bg-emerald-500/10 rounded-md group-hover:bg-emerald-500/20">
                                    <Activity size={14} className="text-emerald-500" />
                                </div>
                                <div className="flex flex-col">
                                    <span className="text-xs font-bold text-slate-200 group-hover:text-white">Split Impact</span>
                                    <span className="text-[10px] text-slate-500 group-hover:text-slate-400">Boundary Analysis</span>
                                </div>
                            </div>
                            <ChevronDown size={14} className="text-slate-600 -rotate-90 group-hover:translate-x-0.5 transition-transform" />
                        </Link>

                        {/* Rainfall Layer Toggle */}
                        <button
                            onClick={onRainfallLayerToggle}
                            aria-pressed={showRainfallLayer}
                            className={`w-full flex items-center justify-between p-3 rounded-lg border transition-all ${showRainfallLayer
                                ? 'bg-blue-500/20 border-blue-500/50'
                                : 'bg-slate-900/50 border-slate-800 hover:border-blue-500/30'
                                }`}
                        >
                            <div className="flex items-center gap-3">
                                <div className={`p-1.5 rounded-md ${showRainfallLayer ? 'bg-blue-500/30' : 'bg-blue-500/10'}`}>
                                    <Calendar size={14} className="text-blue-400" />
                                </div>
                                <div className="flex flex-col text-left">
                                    <span className="text-xs font-bold text-slate-200">Rainfall Layer</span>
                                    <span className="text-[10px] text-slate-500">IMD Normals 1951-2000</span>
                                </div>
                            </div>
                            <div className={`w-10 h-5 rounded-full transition-colors ${showRainfallLayer ? 'bg-blue-500' : 'bg-slate-700'}`}>
                                <div className={`w-4 h-4 rounded-full bg-white shadow-sm transform transition-transform mt-0.5 ${showRainfallLayer ? 'translate-x-5' : 'translate-x-0.5'}`} />
                            </div>
                        </button>
                    </div>

                    {/* 2. Selected District Info & Analytics */}
                    {selectedDistrict ? (
                        <div className="animate-in fade-in slide-in-from-bottom-2 duration-300 glass-card p-4">
                            <div className="flex justify-between items-start mb-2">
                                <h2 className="text-lg font-bold text-white leading-none">{selectedDistrict}</h2>
                                <button
                                    onClick={onClose}
                                    className="text-slate-500 hover:text-white transition-colors"
                                    aria-label="Close details"
                                >
                                    <X size={20} />
                                </button>
                            </div>
                            <div className="flex items-center gap-2 mb-4">
                                <span className="text-slate-400 text-xs font-mono">Year: {currentYear}</span>
                                {(() => {
                                    const raw = bridgeData as Record<string, string>;
                                    const stateKey = Object.keys(raw).find(k => k.startsWith(selectedDistrict + '|'));
                                    const cdk = stateKey ? raw[stateKey] : null;
                                    return cdk ? (
                                        <Link
                                            href={`/compare?districts=${cdk}`}
                                            className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-400 hover:bg-indigo-500/30 transition-colors font-bold uppercase tracking-wider"
                                        >
                                            + Compare
                                        </Link>
                                    ) : null;
                                })()}
                            </div>

                            <div className="text-3xl font-bold text-emerald-400 font-mono tracking-tight mb-4">
                                {districtData?.value != null ? districtData.value.toLocaleString(undefined, { maximumFractionDigits: 1 }) : '—'}
                                <span className="text-xs text-slate-500 ml-2 font-normal uppercase">{currentMetric}</span>
                            </div>

                            {/* Rainfall Data Panel */}
                            {showRainfallLayer && (
                                <div className="glass-panel border-blue-900/40 rounded-lg p-3 mb-4">
                                    <h4 className="text-[10px] text-blue-400 uppercase tracking-widest font-bold mb-2 flex items-center gap-2">
                                        <Calendar size={10} /> Rainfall (IMD 1951-2000)
                                    </h4>
                                    {rainfallLoading ? (
                                        <div className="text-xs text-slate-500">Loading...</div>
                                    ) : rainfallData ? (
                                        <div className="space-y-2">
                                            <div className="flex justify-between">
                                                <span className="text-xs text-slate-400">Annual</span>
                                                <span className="text-sm font-bold text-blue-400">{rainfallData.annual} mm</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-xs text-slate-400">Monsoon (JJAS)</span>
                                                <span className="text-sm font-mono text-blue-300">{rainfallData.seasonal?.monsoon_jjas} mm</span>
                                            </div>
                                            <div className="grid grid-cols-2 gap-2 mt-2 pt-2 border-t border-blue-900/30">
                                                <div className="text-center">
                                                    <div className="text-[10px] text-slate-500">Pre-Monsoon</div>
                                                    <div className="text-xs text-blue-300">{rainfallData.seasonal?.pre_monsoon_mam} mm</div>
                                                </div>
                                                <div className="text-center">
                                                    <div className="text-[10px] text-slate-500">Post-Monsoon</div>
                                                    <div className="text-xs text-blue-300">{rainfallData.seasonal?.post_monsoon_ond} mm</div>
                                                </div>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="text-xs text-slate-500 italic">No rainfall data</div>
                                    )}
                                </div>
                            )}

                            {/* Analytics Chart */}
                            <div className="border-t border-slate-200 pt-4">
                                <h4 className="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-3 flex items-center gap-2">
                                    <Activity size={10} /> Historical Trend
                                </h4>
                                <div className="h-40 w-full -ml-4">
                                    <ReactECharts
                                        option={{
                                            grid: { top: 10, right: 15, bottom: 20, left: 40 },
                                            tooltip: {
                                                trigger: 'axis',
                                                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                                                borderColor: '#e2e8f0',
                                                textStyle: { color: '#0f172a', fontSize: 10 },
                                                padding: [8, 12],
                                                axisPointer: { type: 'line', lineStyle: { color: '#cbd5e1', type: 'dashed' } }
                                            },
                                            xAxis: {
                                                type: 'category',
                                                data: Array.isArray(history) ? history.map(d => d.year) : [],
                                                axisLabel: { color: '#64748b', fontSize: 9 },
                                                axisLine: { show: false },
                                                axisTick: { show: false }
                                            },
                                            yAxis: {
                                                type: 'value',
                                                axisLabel: { color: '#64748b', fontSize: 9, formatter: (val: number) => val >= 1000 ? `${(val / 1000).toFixed(1)}k` : val },
                                                splitLine: { show: false },
                                                axisLine: { show: false }
                                            },
                                            series: [{
                                                data: Array.isArray(history) ? history.map(d => d[currentMetric]) : [],
                                                type: 'line',
                                                smooth: true,
                                                symbol: 'none',
                                                itemStyle: { color: '#10b981' },
                                                lineStyle: { width: 2 }
                                            }]
                                        }}
                                        style={{ height: '100%', width: '100%' }}
                                    />
                                </div>
                            </div>

                            {/* 4. Advanced Analytics Panel */}
                            {(() => {
                                // Resolve CDK and State
                                const raw = bridgeData as Record<string, string>;
                                const stateKey = Object.keys(raw).find(k => k.startsWith(selectedDistrict + '|'));
                                if (stateKey) {
                                    const cdk = raw[stateKey];
                                    const stateName = stateKey.split('|')[1];
                                    return (
                                        <AnalyticsPanel
                                            cdk={cdk}
                                            districtName={selectedDistrict}
                                            state={stateName}
                                            year={currentYear}
                                            crop={currentCrop}
                                        />
                                    );
                                }
                                return null;
                            })()}
                        </div>
                    ) : (
                        <div className="p-8 border border-dashed border-slate-800 rounded-lg text-center flex flex-col items-center justify-center opacity-50">
                            <MapPin size={24} className="text-slate-600 mb-2" />
                            <p className="text-xs text-slate-500 italic max-w-[200px]">Select a district on the map or search to view specific values.</p>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-4 border-t border-slate-900 text-[10px] text-slate-600 font-mono flex justify-between items-center">
                    <span>v1.5 Harmonized</span>
                    <span className="flex items-center gap-1"><span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span> UDP</span>
                </div>
            </div>
        </>
    );
};

export default Dashboard;
