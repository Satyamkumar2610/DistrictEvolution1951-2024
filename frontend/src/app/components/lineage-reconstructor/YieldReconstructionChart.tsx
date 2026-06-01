"use client";

import React, { useMemo } from "react";
import dynamic from "next/dynamic";
import type { PlotMouseEvent } from "plotly.js";

import type { LineageReconstructionEpoch } from "@/app/services/api/types";

// Dynamic import to avoid SSR issues with Plotly
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface ChartTrace {
    x: number[];
    y: Array<number | null>;
    type: "scatter";
    mode: "lines";
    name: string;
    line: {
        color: string;
        width: number;
        shape: "spline";
    };
    fill: "tozeroy" | "none";
    fillcolor?: string;
    hovertemplate: string[];
    connectgaps: boolean;
    showlegend: boolean;
}

interface ChartShape {
    type: "line" | "rect";
    x0: number;
    x1: number;
    y0: number;
    y1: number;
    yref: "paper";
    line?: {
        color?: string;
        width: number;
        dash?: "dot";
    };
    fillcolor?: string;
    layer?: "below";
}

interface ChartAnnotation {
    x: number;
    y: number;
    yref: "paper";
    text: string;
    showarrow: false;
    font: {
        size: number;
        color: string;
        family: string;
    };
}

export default function YieldReconstructionChart({ 
    epochs, 
    activeEpochIndex,
    onEpochChange
}: { 
    epochs: LineageReconstructionEpoch[],
    activeEpochIndex: number,
    onEpochChange: (index: number) => void
}) {
    const { traces, shapes, annotations, yearToEpoch } = useMemo(() => {
        if (!epochs || epochs.length === 0) {
            return { traces: [], shapes: [], annotations: [], yearToEpoch: {} as Record<number, number> };
        }
        const yearToEpochMap: Record<number, number> = {};
        const splitShapes: ChartShape[] = [];
        const splitAnnotations: ChartAnnotation[] = [];

        // Build one trace per epoch for distinct coloring
        const epochTraces: ChartTrace[] = [];

        epochs.forEach((ep, idx) => {
            if (!ep.metrics) return;
            const years: number[] = [];
            const yields: (number | null)[] = [];
            const coverages: string[] = [];
            const productions: string[] = [];

            ep.metrics.forEach((metric) => {
                years.push(metric.year);
                yields.push(metric.collective_yield);
                yearToEpochMap[metric.year] = idx;

                const covPct = metric.data_coverage != null ? `${(metric.data_coverage * 100).toFixed(0)}%` : 'N/A';
                coverages.push(covPct);
                productions.push(
                    metric.collective_production != null
                        ? `${metric.collective_production.toLocaleString()} MT`
                        : 'N/A'
                );
            });

            const isActive = idx === activeEpochIndex;
            // Skip traces with no valid yield data
            const hasAnyYield = yields.some(v => v != null);
            if (!hasAnyYield) return;

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
                // Plotly hovertemplate must be a single string (not an array)
                // Use %{x} and %{y} for per-point substitution
                hovertemplate:
                    `<b>Year: %{x}</b><br>` +
                    `Yield: %{y:.0f} kg/ha<br>` +
                    `<i>Epoch ${ep.epoch_num} · ${ep.year_start}–${ep.year_end ?? 'present'}</i>` +
                    `<extra></extra>`,
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

    const handleClick = (event: Readonly<PlotMouseEvent>) => {
        const clickedYear = event.points?.[0]?.x;
        const year =
            typeof clickedYear === "number"
                ? clickedYear
                : typeof clickedYear === "string"
                    ? Number(clickedYear)
                    : NaN;
        if (Number.isNaN(year)) return;

        const epochIdx = yearToEpoch[year];
        if (epochIdx !== undefined) onEpochChange(epochIdx);
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
