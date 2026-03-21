import React from "react";
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, ReferenceArea
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

    // Flatten all metrics from all epochs into chronological array for the chart
    let fullTimeline: any[] = [];
    const splitYears: {year: number, label: string}[] = [];
    
    epochs.forEach((ep, idx) => {
        if (idx > 0 && ep.year_start) {
            splitYears.push({ year: ep.year_start, label: ep.event_label });
        }
        if (ep.metrics) {
            // Include epoch Index so clicking tooltip triggers onEpochChange
            const annotated = ep.metrics.map((m: any) => ({ ...m, epochIndex: idx }));
            fullTimeline = fullTimeline.concat(annotated);
        }
    });

    const activeEpoch = epochs[activeEpochIndex];
    let highlightStart = activeEpoch?.year_start;
    let highlightEnd = activeEpoch?.year_end || 2024;

    return (
        <div className="w-full h-72">
            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                Yield Reconstruction Timeline (kg/ha)
            </h4>
            <ResponsiveContainer width="100%" height="100%">
                <LineChart 
                    data={fullTimeline} 
                    margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                    onClick={(e: any) => {
                        if (e && e.activePayload && e.activePayload.length > 0) {
                            const payload = e.activePayload[0].payload;
                            if (payload.epochIndex !== undefined) {
                                onEpochChange(payload.epochIndex);
                            }
                        }
                    }}
                >
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis 
                        dataKey="year" 
                        tick={{ fontSize: 10, fill: "#64748b" }} 
                        axisLine={false} 
                        tickLine={false} 
                        type="number"
                        domain={['dataMin', 'dataMax']}
                    />
                    <YAxis 
                        tick={{ fontSize: 10, fill: "#64748b" }} 
                        axisLine={false} 
                        tickLine={false} 
                        width={40}
                        domain={['auto', 'auto']}
                    />
                    <Tooltip
                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                        labelStyle={{ fontWeight: 'bold', color: '#1e293b' }}
                        itemStyle={{ color: '#4f46e5' }}
                        labelFormatter={(label: any) => `Year: ${label}`}
                        formatter={(value: string | number | readonly (string | number)[] | undefined | null, name: any, props: any) => {
                            const cov = props.payload.data_coverage;
                            const covStr = cov !== undefined && cov < 1 ? ` (${(cov*100).toFixed(0)}% coverage)` : '';
                            return [`${value ? value.toLocaleString(undefined, { maximumFractionDigits: 0 }) : 'N/A'}${covStr}`, 'Yield (kg/ha)'];
                        }}
                    />
                    
                    {/* Active highlight band */}
                    {highlightStart !== undefined && (
                        <ReferenceArea 
                            x1={highlightStart} x2={highlightEnd} 
                            fill="#4f46e5" fillOpacity={0.06} 
                        />
                    )}

                    {splitYears.map(sy => (
                        <ReferenceLine 
                            key={sy.year} 
                            x={sy.year} 
                            stroke="#f59e0b" 
                            strokeDasharray="4 4" 
                            label={{ position: 'top', value: sy.label, fill: '#b45309', fontSize: 10 }}
                        />
                    ))}

                    <Line 
                        type="monotone" 
                        dataKey="collective_yield" 
                        stroke="#4f46e5" 
                        strokeWidth={2} 
                        dot={false}
                        activeDot={{ r: 5, fill: '#4f46e5', stroke: '#c7d2fe', strokeWidth: 3 }}
                        connectNulls={false} /* False to enforce gaps when yield is null */
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}
