"use client";

import React, { useState, useEffect } from 'react';
import { 
    fetchAvailableCommodities, 
    fetchPriceTrends, 
    fetchMSPComparison,
    CommodityInfo,
    PriceTrend,
    MSPComparisonResponse 
} from '../../services/api/market';
import { 
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer 
} from 'recharts';
import { IndianRupee, TrendingUp, TrendingDown, Scale, MapPin } from 'lucide-react';
import MSPBadge from './MSPBadge';

export default function MarketDashboard() {
    const [commodities, setCommodities] = useState<CommodityInfo[]>([]);
    
    // State
    const [selectedState, setSelectedState] = useState<string>("Maharashtra");
    const [selectedCrop, setSelectedCrop] = useState<string>("wheat");
    
    // Data
    const [trendData, setTrendData] = useState<PriceTrend | null>(null);
    const [mspData, setMspData] = useState<MSPComparisonResponse | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    // Initial load
    useEffect(() => {
        fetchAvailableCommodities()
            .then(data => setCommodities(data))
            .catch(err => console.error("Could not fetch commodities", err));
    }, []);

    // Fetch data when selection changes
    useEffect(() => {
        async function loadMarketData() {
            setLoading(true);
            setError(null);
            
            try {
                // Fetch in parallel
                const [trend, msp] = await Promise.all([
                    fetchPriceTrends(selectedState, selectedCrop, 30),
                    fetchMSPComparison(selectedState, selectedCrop)
                ]);
                
                setTrendData(trend);
                setMspData(msp);
            } catch (err: any) {
                console.error("Market data fetch error:", err);
                setError(err.message || "Failed to load market data");
            } finally {
                setLoading(false);
            }
        }
        
        loadMarketData();
    }, [selectedState, selectedCrop]);

    // Unique states from commodities (in a real app, this might be a separate API)
    // For now, hardcode major agricultural states for selection
    const availableStates = [
        "Maharashtra", "Punjab", "Haryana", "Madhya Pradesh", 
        "Uttar Pradesh", "Rajasthan", "Gujarat", "Andhra Pradesh", 
        "Telangana", "Karnataka"
    ];

    if (loading && !trendData) {
        return (
            <div className="flex h-full items-center justify-center min-h-[400px]">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-6 max-w-7xl mx-auto w-full pb-10">
            {/* Header & Controls */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-slate-900/50 p-6 rounded-2xl border border-slate-800/50 backdrop-blur-sm">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <IndianRupee className="text-indigo-400" />
                        Agricultural Market Economics
                    </h1>
                    <p className="text-slate-400 text-sm mt-1">Live Mandi prices & MSP benchmarking</p>
                </div>
                
                <div className="flex flex-wrap items-center gap-3">
                    <div className="flex flex-col">
                        <label className="text-[10px] uppercase font-bold text-slate-500 mb-1 ml-1">State</label>
                        <select 
                            value={selectedState}
                            onChange={(e) => setSelectedState(e.target.value)}
                            className="bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block w-full p-2"
                        >
                            {availableStates.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                    </div>
                    <div className="flex flex-col">
                        <label className="text-[10px] uppercase font-bold text-slate-500 mb-1 ml-1">Commodity</label>
                        <select 
                            value={selectedCrop}
                            onChange={(e) => setSelectedCrop(e.target.value)}
                            className="bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block w-full p-2"
                        >
                            {/* Grouping crops typically found in our data */}
                            <optgroup label="Cereals">
                                <option value="wheat">Wheat</option>
                                <option value="rice">Rice / Paddy</option>
                                <option value="maize">Maize</option>
                                <option value="sorghum">Sorghum (Jowar)</option>
                                <option value="pearl_millet">Pearl Millet (Bajra)</option>
                            </optgroup>
                            <optgroup label="Pulses">
                                <option value="chickpea">Chickpea (Gram)</option>
                                <option value="pigeonpea">Pigeonpea (Tur)</option>
                                <option value="moong">Moong</option>
                            </optgroup>
                            <optgroup label="Oilseeds">
                                <option value="soyabean">Soyabean</option>
                                <option value="groundnut">Groundnut</option>
                                <option value="rapeseed_and_mustard">Mustard</option>
                            </optgroup>
                            <optgroup label="Cash Crops">
                                <option value="cotton">Cotton</option>
                                <option value="sugarcane">Sugarcane</option>
                            </optgroup>
                        </select>
                    </div>
                </div>
            </div>

            {error && (
                <div className="bg-rose-500/10 border border-rose-500/20 text-rose-400 p-4 rounded-xl">
                    ⚠️ {error}
                </div>
            )}

            {/* Quick Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-slate-900/40 p-6 rounded-2xl border border-slate-800/50 backdrop-blur-sm relative overflow-hidden group">
                    <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                    <h3 className="text-slate-400 text-sm font-medium mb-1">State Avg. Modal Price</h3>
                    <div className="flex items-end gap-2">
                        <span className="text-3xl font-bold text-white">
                            {mspData?.state_avg_modal_price ? `₹${mspData.state_avg_modal_price}` : "—"}
                        </span>
                        <span className="text-slate-500 text-sm mb-1">/ quintal</span>
                    </div>
                    {trendData?.price_change_pct && (
                        <div className={`flex items-center gap-1 mt-2 text-sm font-medium ${trendData.price_change_pct > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                            {trendData.price_change_pct > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                            {Math.abs(trendData.price_change_pct)}% over 30 days
                        </div>
                    )}
                </div>

                <div className="bg-slate-900/40 p-6 rounded-2xl border border-slate-800/50 backdrop-blur-sm relative overflow-hidden group">
                    <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                    <h3 className="text-slate-400 text-sm font-medium mb-1 flex justify-between items-center">
                        Official MSP (Govt Support Price)
                        <span className="text-xs bg-slate-800 px-2 py-0.5 rounded text-slate-300">
                            {mspData?.msp?.year || "Current"}
                        </span>
                    </h3>
                    <div className="flex items-end gap-2">
                        <span className="text-3xl font-bold text-white">
                            {mspData?.msp?.msp_price ? `₹${mspData.msp.msp_price}` : "—"}
                        </span>
                        <span className="text-slate-500 text-sm mb-1">/ quintal</span>
                    </div>
                    <div className="flex items-center gap-1 mt-2 text-sm text-slate-400">
                        <Scale size={14} />
                        Recommended floor price
                    </div>
                </div>

                <div className="bg-slate-900/40 p-6 rounded-2xl border border-slate-800/50 backdrop-blur-sm relative overflow-hidden group">
                    <div className={`absolute inset-0 bg-gradient-to-br opacity-0 group-hover:opacity-100 transition-opacity ${
                        (mspData?.state_avg_ratio || 0) >= 1 ? "from-emerald-500/5" : "from-rose-500/5"
                    }`} />
                    <h3 className="text-slate-400 text-sm font-medium mb-1">State Premium / Deficit</h3>
                    {mspData?.state_avg_ratio ? (
                        <>
                            <div className="flex items-end gap-2">
                                <span className={`text-3xl font-bold ${mspData.state_avg_ratio >= 1.0 ? "text-emerald-400" : "text-rose-400"}`}>
                                    {mspData.state_avg_ratio >= 1.0 ? "+" : ""}{((mspData.state_avg_ratio - 1) * 100).toFixed(1)}%
                                </span>
                            </div>
                            <div className="flex items-center gap-1 mt-2 text-sm text-slate-400">
                                vs. Official MSP Benchmark
                            </div>
                        </>
                    ) : (
                        <div className="text-3xl font-bold text-slate-600">—</div>
                    )}
                </div>
            </div>

            {/* Price Trend Chart */}
            <div className="bg-slate-900/40 p-6 rounded-2xl border border-slate-800/50 backdrop-blur-sm">
                <h3 className="text-white font-semibold mb-6 flex items-center gap-2">
                    <TrendingUp className="text-indigo-400" size={18} />
                    30-Day Mandi Price Trend
                </h3>
                
                {trendData && trendData.data_points.length > 0 ? (
                    <div className="h-72 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={trendData.data_points} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                                <defs>
                                    <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                                <XAxis 
                                    dataKey="date" 
                                    stroke="#64748b" 
                                    fontSize={12} 
                                    tickFormatter={(val) => {
                                        const d = new Date(val);
                                        return `${d.getDate()} ${d.toLocaleString('default', { month: 'short' })}`;
                                    }}
                                />
                                <YAxis 
                                    stroke="#64748b" 
                                    fontSize={12} 
                                    domain={['auto', 'auto']}
                                    tickFormatter={(val) => `₹${val}`}
                                />
                                <RechartsTooltip 
                                    contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc', borderRadius: '8px' }}
                                    formatter={(value: any) => [`₹${value}`, 'Avg Price']}
                                    labelFormatter={(label) => new Date(label).toLocaleDateString()}
                                />
                                {/* Overlay MSP Reference Line if available */}
                                {mspData?.msp?.msp_price && (
                                    <Area 
                                        type="step" 
                                        dataKey={() => mspData.msp.msp_price} 
                                        stroke="#10b981" 
                                        strokeDasharray="5 5" 
                                        fill="none" 
                                        name="MSP Benchmark"
                                    />
                                )}
                                <Area 
                                    type="monotone" 
                                    dataKey="avg_modal_price" 
                                    stroke="#6366f1" 
                                    strokeWidth={3}
                                    fillOpacity={1} 
                                    fill="url(#priceGradient)" 
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                ) : (
                    <div className="h-72 flex items-center justify-center text-slate-500 border border-dashed border-slate-700 rounded-xl">
                        No trend data available for this selection
                    </div>
                )}
            </div>

            {/* District MSP Comparison Table */}
            <div className="bg-slate-900/40 rounded-2xl border border-slate-800/50 backdrop-blur-sm overflow-hidden">
                <div className="p-6 border-b border-slate-800/50">
                    <h3 className="text-white font-semibold flex items-center gap-2">
                        <MapPin className="text-indigo-400" size={18} />
                        District Market Performance vs. MSP
                    </h3>
                </div>
                
                <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                        <thead className="bg-slate-800/50 text-slate-400 uppercase text-[10px] font-bold tracking-wider">
                            <tr>
                                <th className="px-6 py-4">District</th>
                                <th className="px-6 py-4">Avg Market Price</th>
                                <th className="px-6 py-4">Status</th>
                                <th className="px-6 py-4">Premium / Deficit</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/50">
                            {mspData?.districts && mspData.districts.length > 0 ? (
                                mspData.districts.map((d, i) => (
                                    <tr key={i} className="hover:bg-slate-800/20 transition-colors">
                                        <td className="px-6 py-4 font-medium text-slate-200">
                                            {d.district}
                                        </td>
                                        <td className="px-6 py-4 text-white">
                                            ₹{d.avg_modal_price}
                                        </td>
                                        <td className="px-6 py-4">
                                            <MSPBadge status={d.status} />
                                        </td>
                                        <td className={`px-6 py-4 font-medium ${d.premium_or_deficit_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                            {d.premium_or_deficit_pct > 0 ? "+" : ""}{d.premium_or_deficit_pct}%
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={4} className="px-6 py-8 text-center text-slate-500">
                                        No district-level data available for this selection
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
            
        </div>
    );
}
