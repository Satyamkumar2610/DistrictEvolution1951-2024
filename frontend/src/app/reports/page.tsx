'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';
import { FileText, Download, Eye, Search, ChevronRight } from 'lucide-react';

const REPORT_TYPES = [
    { id: 'district-profile', label: 'District Profile', desc: 'Comprehensive metrics, yield history, and state benchmarks' },
    { id: 'risk-assessment', label: 'Risk Assessment', desc: 'Anomaly scan, volatility analysis, and risk scoring' },
];

const CROPS = [
    { value: 'wheat', label: 'Wheat' },
    { value: 'rice', label: 'Rice' },
    { value: 'maize', label: 'Maize' },
    { value: 'cotton', label: 'Cotton' },
    { value: 'soyabean', label: 'Soybean' },
    { value: 'sugarcane', label: 'Sugarcane' },
];

export default function ReportsPage() {
    const [reportType, setReportType] = useState('district-profile');
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedCdk, setSelectedCdk] = useState<string>('');
    const [selectedCrop, setSelectedCrop] = useState('wheat');
    const [previewOpen, setPreviewOpen] = useState(false);

    // Search districts
    const {
        data: searchResults,
        isFetching: searchingDistricts,
        isError: searchError,
    } = useQuery({
        queryKey: ['search', searchQuery],
        queryFn: () => api.searchDistricts(searchQuery, 'district'),
        enabled: searchQuery.length >= 2,
    });

    // Generate report
    const { data: report, isLoading: generating, isError: reportError } = useQuery({
        queryKey: ['report', reportType, selectedCdk, selectedCrop],
        queryFn: () => api.getDistrictReport(selectedCdk, selectedCrop, 'json'),
        enabled: !!selectedCdk && previewOpen,
    });

    const handleDownloadJSON = () => {
        if (!report) return;
        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${report.district?.name || 'report'}_${selectedCrop}_profile.json`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const handleDownloadCSV = () => {
        if (!report?.yearly_data) return;
        const headers = Object.keys(report.yearly_data[0] || {}).join(',');
        const rows = report.yearly_data.map((row: Record<string, unknown>) => Object.values(row).join(','));
        const csv = [headers, ...rows].join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${report.district?.name || 'report'}_${selectedCrop}_data.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <main className="page-container">
            <div className="mb-6">
                <div className="flex items-center gap-3 mb-1">
                    <FileText className="text-indigo-600" size={24} />
                    <h1 className="text-2xl font-bold text-slate-900">Report Builder</h1>
                </div>
                <p className="text-slate-500 text-sm mb-3">Generate and download analytical reports</p>
                <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-3 text-xs text-indigo-800 font-medium">
                    <strong>Note on Data Continuity:</strong> These reports automatically adjust for historical district boundary changes. By accounting for the 565+ split events since 1951, the metrics presented here reflect genuine agronomic performance rather than statistical artifacts caused by administrative restructuring.
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left: Configuration */}
                <div className="lg:col-span-1 space-y-6">
                    {/* Report Type */}
                    <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-5">
                        <h3 className="section-header">Report Type</h3>
                        <div className="space-y-2">
                            {REPORT_TYPES.map((type) => (
                                <button
                                    key={type.id}
                                    onClick={() => setReportType(type.id)}
                                    className={`w-full text-left p-3 rounded-lg border transition ${reportType === type.id
                                        ? 'bg-indigo-50 border-indigo-200'
                                        : 'bg-slate-50 border-slate-200 hover:border-indigo-300'
                                        }`}
                                >
                                    <div className="text-sm font-medium text-slate-900">{type.label}</div>
                                    <div className="text-xs text-slate-500 mt-0.5 font-medium">{type.desc}</div>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* District Search */}
                    <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-5">
                        <h3 className="section-header">Select District</h3>
                        <div className="relative mb-3">
                            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                placeholder="Search districts..."
                                className="w-full bg-slate-50 border border-slate-200 text-slate-900 rounded-lg pl-9 pr-4 py-2 text-sm focus:border-indigo-600 outline-none transition"
                            />
                        </div>
                        {searchResults && searchQuery.length >= 2 && (
                            <div className="max-h-[200px] overflow-y-auto custom-scrollbar space-y-1">
                                {searchResults.results.map((r, i) => (
                                    <button
                                        key={i}
                                        onClick={() => { setSelectedCdk(r.cdk || ''); setSearchQuery(r.name); setPreviewOpen(false); }}
                                        className={`w-full flex items-center justify-between p-2 rounded-lg text-left transition ${selectedCdk === r.cdk ? 'bg-indigo-50 border border-indigo-200' : 'hover:bg-slate-100'
                                            }`}
                                    >
                                        <div>
                                            <div className="text-sm text-slate-900 font-medium">{r.name}</div>
                                            <div className="text-[10px] text-slate-500 font-bold">{r.state}</div>
                                        </div>
                                        <ChevronRight size={14} className="text-slate-600" />
                                    </button>
                                ))}
                            </div>
                        )}
                        {searchQuery.length >= 2 && searchingDistricts && (
                            <p className="text-xs text-slate-500 font-medium">Searching districts...</p>
                        )}
                        {searchQuery.length >= 2 && searchError && (
                            <p className="text-xs text-rose-600 font-medium">
                                District search failed. Please retry.
                            </p>
                        )}
                        {searchQuery.length >= 2 && !searchingDistricts && !searchError && searchResults?.results.length === 0 && (
                            <p className="text-xs text-slate-500 font-medium">
                                No districts matched &quot;{searchQuery}&quot;.
                            </p>
                        )}
                        {!selectedCdk && searchQuery.length > 0 && (
                            <p className="mt-2 text-xs text-slate-500 font-medium">
                                Type at least two characters and choose a district from the results to enable report generation.
                            </p>
                        )}
                        {selectedCdk && (
                            <div className="mt-3 p-2 rounded-lg bg-indigo-50 border border-indigo-200 text-xs text-indigo-800 font-medium">
                                Selected: {searchQuery} ({selectedCdk})
                            </div>
                        )}
                    </div>

                    {/* Crop Selector */}
                    <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-5">
                        <h3 className="section-header">Crop</h3>
                        <select
                            value={selectedCrop}
                            onChange={(e) => setSelectedCrop(e.target.value)}
                            className="w-full bg-slate-50 border border-slate-200 text-slate-900 rounded-lg px-4 py-2 text-sm focus:border-indigo-600 outline-none transition"
                        >
                            {CROPS.map((c) => (
                                <option key={c.value} value={c.value}>{c.label}</option>
                            ))}
                        </select>
                    </div>

                    {/* Generate Button */}
                    <button
                        onClick={() => setPreviewOpen(true)}
                        disabled={!selectedCdk}
                        className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl font-medium text-sm transition ${selectedCdk
                            ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white hover:from-indigo-500 hover:to-purple-500 shadow-lg shadow-indigo-500/20'
                            : 'bg-slate-800 text-slate-500 cursor-not-allowed'
                            }`}
                    >
                        <Eye size={16} />
                        Generate & Preview
                    </button>
                </div>

                {/* Right: Preview */}
                <div className="lg:col-span-2">
                    {!previewOpen && (
                        <div className="text-center py-20 bg-white border border-slate-200 shadow-sm rounded-xl">
                            <FileText className="mx-auto text-slate-500 mb-4" size={48} />
                            <p className="text-slate-500 text-sm font-medium">Configure report parameters and click Generate</p>
                        </div>
                    )}

                    {generating && previewOpen && (
                        <div className="flex items-center justify-center py-20 bg-white border border-slate-200 shadow-sm rounded-xl">
                            <div className="flex flex-col items-center gap-3">
                                <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                                <span className="text-sm font-medium text-slate-500">Generating report...</span>
                            </div>
                        </div>
                    )}

                    {reportError && previewOpen && (
                        <div className="bg-white border border-rose-200 rounded-xl p-10 text-center shadow-sm">
                            <FileText size={36} className="mx-auto mb-3 text-rose-300" />
                            <h3 className="text-lg font-bold text-slate-700">Report Generation Failed</h3>
                            <p className="text-sm text-slate-500 mt-1">Unable to generate report. The district may not have data for this crop.</p>
                        </div>
                    )}

                    {report && previewOpen && !generating && (
                        <div className="space-y-6 animate-in">
                            {/* Download Actions */}
                            <div className="flex gap-3">
                                <button
                                    onClick={handleDownloadJSON}
                                    className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm hover:bg-emerald-500 transition"
                                >
                                    <Download size={14} />
                                    Download JSON
                                </button>
                                <button
                                    onClick={handleDownloadCSV}
                                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-500 transition"
                                >
                                    <Download size={14} />
                                    Download CSV
                                </button>
                            </div>

                            {/* Report Header */}
                            <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-5">
                                <h2 className="text-lg font-bold text-slate-900 mb-1">{report.district?.name}</h2>
                                <div className="text-sm text-slate-500 font-medium">{report.district?.state} • <span className="capitalize">{report.crop}</span> • Profile Report</div>
                            </div>

                            {/* Statistics */}
                            {report.statistics && (
                                <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-5">
                                    <h3 className="section-header">Key Statistics</h3>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                        <div>
                                            <div className="text-xs text-slate-500">Mean Yield</div>
                                            <div className="text-lg font-bold text-emerald-400">{report.statistics.mean_yield} <span className="text-xs text-slate-500">kg/ha</span></div>
                                        </div>
                                        <div>
                                            <div className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">Max Yield</div>
                                            <div className="text-lg font-bold text-blue-600">{report.statistics.max_yield}</div>
                                        </div>
                                        <div>
                                            <div className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">Min Yield</div>
                                            <div className="text-lg font-bold text-amber-600">{report.statistics.min_yield}</div>
                                        </div>
                                        <div>
                                            <div className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">CV (%)</div>
                                            <div className="text-lg font-bold text-red-600">{report.statistics.cv_yield || '—'}</div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* State Benchmark */}
                            {report.state_benchmark && (
                                <div className="bg-white border border-slate-200 shadow-sm rounded-xl p-5">
                                    <h3 className="section-header">State Benchmark</h3>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <div className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">State Avg Yield</div>
                                            <div className="text-lg font-bold text-slate-900">{report.state_benchmark.avg_yield} <span className="text-xs text-slate-500">kg/ha</span></div>
                                        </div>
                                        <div>
                                            <div className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">Rel. Efficiency</div>
                                            <div className={`text-lg font-bold ${report.state_benchmark.efficiency > 1 ? 'text-emerald-600' : 'text-rose-600'}`}>
                                                {report.state_benchmark.efficiency?.toFixed(3) || '—'}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Yearly Data Table */}
                            {report.yearly_data && report.yearly_data.length > 0 && (
                                <div className="bg-white border border-slate-200 shadow-sm rounded-xl overflow-hidden">
                                    <div className="px-5 py-4 border-b border-slate-200 bg-slate-50">
                                        <h3 className="section-header mb-0">Yearly Data ({report.yearly_data.length} years)</h3>
                                    </div>
                                    <div className="overflow-x-auto max-h-[400px] overflow-y-auto custom-scrollbar">
                                        <table className="w-full text-sm">
                                            <thead className="text-xs text-slate-500 uppercase bg-slate-50 sticky top-0 border-b border-slate-200 shadow-sm">
                                                <tr>
                                                    <th className="px-4 py-2 text-left font-bold">Year</th>
                                                    <th className="px-4 py-2 text-right font-bold">Yield</th>
                                                    <th className="px-4 py-2 text-right font-bold">Area</th>
                                                    <th className="px-4 py-2 text-right font-bold">Production</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-slate-100">
                                                {report.yearly_data.map((row: { year: number; yield?: number; area?: number; production?: number }, i: number) => (
                                                    <tr key={i} className="hover:bg-slate-50/50 transition">
                                                        <td className="px-4 py-2 text-slate-900 font-bold font-mono">{row.year}</td>
                                                        <td className="px-4 py-2 text-right font-bold text-emerald-600">{row.yield?.toFixed(0) || '—'}</td>
                                                        <td className="px-4 py-2 text-right text-slate-500 font-medium">{row.area?.toFixed(0) || '—'}</td>
                                                        <td className="px-4 py-2 text-right text-slate-500 font-medium">{row.production?.toFixed(0) || '—'}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </main>
    );
}
