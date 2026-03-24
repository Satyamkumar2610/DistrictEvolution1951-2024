import React from "react";
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, ReferenceArea
} from "recharts";

export default function YieldReconstructionChart({ 
    epochs, 
    activeEpochIndex,
    onEpochChange
}: { 
    epochs: any[],
    activeEpochIndex: number,
    onEpochChange: (index: number) => void
}) {
    if (!epochs || epochs.length === 0) return null;

    // Flatten all metrics
    let fullTimeline: any[] = [];
    const splitYears: {year: number, label: string}[] = [];
    
    epochs.forEach((ep, idx) => {
        if (idx > 0 && ep.year_start) {
            splitYears.push({ year: ep.year_start, label: ep.event_label });
        }
        if (ep.metrics) {
            const annotated = ep.metrics.map((m: any) => ({ ...m, epochIndex: idx }));
            fullTimeline = fullTimeline.concat(annotated);
        }
    });

    const activeEpoch = epochs[activeEpochIndex];
    const highlightStart = activeEpoch?.year_start;
    const highlightEnd = activeEpoch?.year_end || 2024;

    return (
        <div className="w-full h-full flex flex-col">
            <div className="flex items-center justify-between mb-3">
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                    Yield Timeline
                </h4>
                <span className="text-[10px] text-slate-600">kg/ha • click to navigate</span>
            </div>
            <div className="flex-1 min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart 
                        data={fullTimeline} 
                        margin={{ top: 10, right: 10, left: -10, bottom: 0 }}
                        onClick={(e: any) => {
                            if (e?.activePayload?.[0]?.payload?.epochIndex !== undefined) {
                                onEpochChange(e.activePayload[0].payload.epochIndex);
                            }
                        }}
                    >
                        <defs>
                            <linearGradient id="yieldGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3}/>
                                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.02}/>
                            </linearGradient>
                        </defs>

                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#1e293b" />
                        <XAxis 
                            dataKey="year" 
                            tick={{ fontSize: 10, fill: "#475569" }} 
                            axisLine={false} 
                            tickLine={false} 
                            type="number"
                            domain={['dataMin', 'dataMax']}
                        />
                        <YAxis 
                            tick={{ fontSize: 10, fill: "#475569" }} 
                            axisLine={false} 
                            tickLine={false} 
                            width={40}
                            domain={['auto', 'auto']}
                        />
                        <Tooltip
                            contentStyle={{ 
                                backgroundColor: '#0f172a', 
                                borderRadius: '12px', 
                                border: '1px solid #1e293b', 
                                boxShadow: '0 25px 50px -12px rgb(0 0 0 / 0.5)',
                                padding: '10px 14px',
                            }}
                            labelStyle={{ fontWeight: 'bold', color: '#e2e8f0', fontSize: '12px' }}
                            itemStyle={{ color: '#a78bfa' }}
                            labelFormatter={(label: any) => `Year: ${label}`}
                            formatter={(value: any, name: any, props: any) => {
                                const cov = props.payload.data_coverage;
                                const covStr = cov !== undefined && cov < 1 ? ` (${(cov*100).toFixed(0)}% cov.)` : '';
                                return [`${value ? Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 }) : 'N/A'}${covStr}`, 'Yield (kg/ha)'];
                            }}
                            cursor={{ stroke: '#6366f1', strokeWidth: 1, strokeDasharray: '4 4' }}
                        />
                        
                        {/* Active epoch highlight */}
                        {highlightStart !== undefined && (
                            <ReferenceArea 
                                x1={highlightStart} x2={highlightEnd} 
                                fill="#6366f1" fillOpacity={0.06} 
                            />
                        )}

                        {/* Split year markers */}
                        {splitYears.map(sy => (
                            <ReferenceLine 
                                key={sy.year} 
                                x={sy.year} 
                                stroke="#f59e0b" 
                                strokeDasharray="4 4"
                                strokeWidth={1.5}
                                label={{ 
                                    position: 'top', 
                                    value: `${sy.year}`, 
                                    fill: '#f59e0b', 
                                    fontSize: 9,
                                    fontWeight: 700,
                                }}
                            />
                        ))}

                        <Area 
                            type="monotone" 
                            dataKey="collective_yield" 
                            stroke="#8b5cf6" 
                            strokeWidth={2} 
                            fill="url(#yieldGradient)"
                            dot={false}
                            activeDot={{ r: 5, fill: '#8b5cf6', stroke: '#1e1b4b', strokeWidth: 3 }}
                            connectNulls={false}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
