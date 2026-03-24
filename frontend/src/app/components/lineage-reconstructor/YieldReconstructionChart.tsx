"use client";

import React, { useMemo } from "react";
import dynamic from "next/dynamic";

// Dynamic import to avoid SSR issues with Plotly
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export default function YieldReconstructionChart({ 
    epochs, 
    activeEpochIndex,
    onEpochChange
}: { 
    epochs: any[],
    activeEpochIndex: number,
    onEpochChange: (index: number) => void
}) {
    const { traces, shapes, annotations, yearToEpoch } = useMemo(() => {
        if (!epochs || epochs.length === 0) {
            return { traces: [], shapes: [], annotations: [], yearToEpoch: {} as Record<number, number> };
        }
        const yearToEpochMap: Record<number, number> = {};
        const splitShapes: any[] = [];
        const splitAnnotations: any[] = [];

        // Build one trace per epoch for distinct coloring
        const epochTraces: any[] = [];

        epochs.forEach((ep, idx) => {
            if (!ep.metrics) return;
            const years: number[] = [];
            const yields: (number | null)[] = [];
            const coverages: string[] = [];
            const productions: string[] = [];

            ep.metrics.forEach((m: any) => {
                years.push(m.year);
                yields.push(m.collective_yield);
                yearToEpochMap[m.year] = idx;

                const covPct = m.data_coverage != null ? `${(m.data_coverage * 100).toFixed(0)}%` : 'N/A';
                coverages.push(covPct);
                productions.push(m.collective_production ? `${m.collective_production.toLocaleString()} MT` : 'N/A');
            });

            const isActive = idx === activeEpochIndex;

            epochTraces.push({
                x: years,
                y: yields,
                type: 'scatter',
                mode: 'lines',
                name: `Epoch ${ep.epoch_num}`,
                line: {
                    color: isActive ? '#8b5cf6' : '#475569',
                    width: isActive ? 3 : 1.5,
                    shape: 'spline',
                },
                fill: isActive ? 'tozeroy' : 'none',
                fillcolor: isActive ? 'rgba(139, 92, 246, 0.08)' : undefined,
                hovertemplate: years.map((y, i) => 
                    `<b>Year: ${y}</b><br>` +
                    `Yield: ${yields[i] != null ? `${yields[i]!.toLocaleString()} kg/ha` : 'N/A'}<br>` +
                    `Production: ${productions[i]}<br>` +
                    `Coverage: ${coverages[i]}<br>` +
                    `<i>Epoch ${ep.epoch_num}</i>` +
                    `<extra></extra>`
                ),
                connectgaps: false,
                showlegend: false,
            });

            // Add split event markers
            if (idx > 0 && ep.year_start) {
                splitShapes.push({
                    type: 'line',
                    x0: ep.year_start,
                    x1: ep.year_start,
                    y0: 0,
                    y1: 1,
                    yref: 'paper',
                    line: {
                        color: '#f59e0b',
                        width: 2,
                        dash: 'dot',
                    },
                });
                splitAnnotations.push({
                    x: ep.year_start,
                    y: 1.06,
                    yref: 'paper',
                    text: `<b>${ep.year_start}</b>`,
                    showarrow: false,
                    font: { size: 9, color: '#f59e0b', family: 'Inter, system-ui, sans-serif' },
                });
            }
        });

        // Active epoch highlight band
        const activeEp = epochs[activeEpochIndex];
        if (activeEp) {
            splitShapes.push({
                type: 'rect',
                x0: activeEp.year_start,
                x1: activeEp.year_end || 2024,
                y0: 0,
                y1: 1,
                yref: 'paper',
                fillcolor: 'rgba(99, 102, 241, 0.06)',
                line: { width: 0 },
                layer: 'below',
            });
        }

        return {
            traces: epochTraces,
            shapes: splitShapes,
            annotations: splitAnnotations,
            yearToEpoch: yearToEpochMap,
        };
    }, [epochs, activeEpochIndex]);

    const handleClick = (event: any) => {
        if (event?.points?.[0]?.x) {
            const yr = event.points[0].x;
            const epochIdx = yearToEpoch[yr];
            if (epochIdx !== undefined) onEpochChange(epochIdx);
        }
    };

    if (traces.length === 0) return null;

    return (
        <div className="w-full h-full flex flex-col">
            <div className="flex items-center justify-between mb-2">
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                    Yield Timeline
                </h4>
                <span className="text-[10px] text-slate-600">zoom • pan • click to navigate</span>
            </div>
            <div className="flex-1 min-h-0">
                <Plot
                    data={traces}
                    layout={{
                        autosize: true,
                        margin: { t: 20, r: 15, b: 40, l: 50 },
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        font: {
                            family: 'Inter, system-ui, sans-serif',
                            color: '#94a3b8',
                            size: 11,
                        },
                        xaxis: {
                            showgrid: false,
                            zeroline: false,
                            tickfont: { size: 10, color: '#475569' },
                            linecolor: '#1e293b',
                            dtick: 10,
                            rangeslider: {
                                visible: true,
                                thickness: 0.06,
                                bgcolor: '#0f172a',
                                bordercolor: '#1e293b',
                            },
                        },
                        yaxis: {
                            title: { text: 'kg/ha', font: { size: 10, color: '#64748b' }, standoff: 5 },
                            showgrid: true,
                            gridcolor: '#1e293b',
                            gridwidth: 1,
                            zeroline: false,
                            tickfont: { size: 10, color: '#475569' },
                            linecolor: '#1e293b',
                        },
                        shapes,
                        annotations,
                        hovermode: 'x unified',
                        hoverlabel: {
                            bgcolor: '#0f172a',
                            bordercolor: '#334155',
                            font: { family: 'Inter, system-ui, sans-serif', size: 11, color: '#e2e8f0' },
                        },
                        dragmode: 'zoom',
                        showlegend: false,
                    }}
                    config={{
                        displayModeBar: true,
                        modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
                        displaylogo: false,
                        responsive: true,
                    }}
                    style={{ width: '100%', height: '100%' }}
                    useResizeHandler
                    onClick={handleClick}
                />
            </div>
        </div>
    );
}
