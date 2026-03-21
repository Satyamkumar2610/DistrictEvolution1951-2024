import React from 'react';

export default function EpochMetricsPanel({ 
    epoch, 
    crop 
}: { 
    epoch: any, 
    crop: string 
}) {
    if (!epoch) return null;

    // The epoch parameter contains the array of metrics for each year. We will aggregate them 
    // to show an epoch "average" or just peak values, or the UI spec says "Metrics Strip".
    // Alternatively, if metrics are per year, the visual needs a summary. 
    // Spec: "Collective yield (kg/ha)", "Total production (MT)", "Total area (ha)"
    // The panel needs single values. We can use the most recent year's data in the epoch, or averages.
    // Wait, the spec says "Metrics panel", doesn't specify if it's for the single YEAR or the whole EPOCH.
    // Typically, it shows the latest year's value in the active epoch.
    const latestMetric = epoch.metrics && epoch.metrics.length > 0 
        ? epoch.metrics[epoch.metrics.length - 1] 
        : null;

    const yieldVal = latestMetric?.collective_yield;
    const prodVal = latestMetric?.collective_production;
    const areaVal = latestMetric?.collective_area;
    const coverage = latestMetric?.data_coverage;

    return (
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm flex flex-col gap-4">
            <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wide">Epoch Metrics (Latest year in epoch)</h3>
            
            <div className="grid grid-cols-3 gap-4">
                <div className="p-3 bg-indigo-50 rounded-md border border-indigo-100">
                    <p className="text-xs text-indigo-600 font-semibold mb-1">Collective Yield</p>
                    <p className="text-xl font-bold text-slate-900">
                        {yieldVal ? `${yieldVal.toLocaleString(undefined, { maximumFractionDigits: 0 })} kg/ha` : "N/A"}
                    </p>
                </div>
                <div className="p-3 bg-indigo-50 rounded-md border border-indigo-100">
                    <p className="text-xs text-indigo-600 font-semibold mb-1">Total {crop} Production</p>
                    <p className="text-xl font-bold text-slate-900">
                        {prodVal ? `${prodVal.toLocaleString(undefined, { maximumFractionDigits: 0 })} MT` : "N/A"}
                    </p>
                </div>
                <div className="p-3 bg-indigo-50 rounded-md border border-indigo-100">
                    <p className="text-xs text-indigo-600 font-semibold mb-1">Total {crop} Area</p>
                    <p className="text-xl font-bold text-slate-900">
                        {areaVal ? `${areaVal.toLocaleString(undefined, { maximumFractionDigits: 0 })} ha` : "N/A"}
                    </p>
                </div>
            </div>

            <div className="flex flex-col gap-2 mt-2">
                <div className="flex flex-wrap gap-2">
                    <span className="text-xs font-semibold text-slate-500 py-1">Active Districts:</span>
                    {epoch.active_cdks.map((cdk: string, i: number) => (
                        <span key={i} className="px-2 py-1 bg-slate-100 text-slate-600 text-xs rounded-md border border-slate-200 cursor-pointer hover:bg-slate-200 transition">
                            {cdk}
                        </span>
                    ))}
                </div>

                {epoch.is_virtual && (
                    <div className="mt-2 inline-flex items-center px-2 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded border border-blue-200 w-max">
                        Informational: Reconstructed parent
                    </div>
                )}
                
                {coverage !== undefined && coverage < 1 && coverage > 0 && (
                    <div className="mt-1 inline-flex items-center px-2 py-1 bg-yellow-50 text-yellow-700 text-xs font-medium rounded border border-yellow-200 w-max">
                        Partial data — {(coverage * 100).toFixed(0)}% of components covered
                    </div>
                )}

                {yieldVal === null && (
                    <div className="mt-1 inline-flex items-center px-2 py-1 bg-slate-50 text-slate-500 text-xs font-medium rounded border border-slate-200 w-max">
                        No agricultural data for this period
                    </div>
                )}
            </div>
        </div>
    );
}
