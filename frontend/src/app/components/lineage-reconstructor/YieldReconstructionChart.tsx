import React from "react";
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine
} from "recharts";

interface TimelinePoint {
    year: number;
    yield_kg_ha: number | null;
    is_split_year: boolean;
    active_cdks: string[];
}

interface Props {
    data: TimelinePoint[];
    crop: string;
}

export default function YieldReconstructionChart({ data, crop }: Props) {
    if (!data || data.length === 0) return null;

    const splitYears = data.filter(d => d.is_split_year).map(d => d.year);

    return (
        <div className="w-full h-64 mt-4">
            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                Reconstructed {crop} Yield (kg/ha)
            </h4>
            <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis 
                        dataKey="year" 
                        tick={{ fontSize: 10, fill: "#64748b" }} 
                        axisLine={false} 
                        tickLine={false} 
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
                        formatter={(value: string | number | readonly (string | number)[] | undefined | null) => [value ? value.toLocaleString() : 'N/A', 'Yield (kg/ha)']}
                        labelFormatter={(label: any) => `Year: ${label}`}
                    />
                    {splitYears.map(year => (
                        <ReferenceLine 
                            key={year} 
                            x={year} 
                            stroke="#f59e0b" 
                            strokeDasharray="3 3" 
                            label={{ position: 'top', value: 'Split', fill: '#f59e0b', fontSize: 10 }}
                        />
                    ))}
                    <Line 
                        type="monotone" 
                        dataKey="yield_kg_ha" 
                        stroke="#4f46e5" 
                        strokeWidth={2} 
                        dot={{ r: 3, fill: '#4f46e5', strokeWidth: 0 }} 
                        activeDot={{ r: 5, fill: '#4f46e5', stroke: '#c7d2fe', strokeWidth: 3 }}
                        connectNulls
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}
