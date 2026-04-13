"use client";

import React, { useState } from 'react';

interface TimeSliderProps {
    minYear: number;
    maxYear: number;
    currentYear: number;
    onChange: (year: number) => void;
    coverageByYear?: Record<number, number>;
}

function getCoverageClass(coverage: number | undefined): { color: string; label: string } {
    if (coverage === undefined) return { color: 'bg-slate-600', label: 'No coverage data' };
    if (coverage > 0.5) return { color: 'bg-emerald-400', label: `${Math.round(coverage * 100)}% districts covered` };
    if (coverage >= 0.2) return { color: 'bg-amber-400', label: `Sparse data (${Math.round(coverage * 100)}% covered)` };
    return { color: 'bg-slate-500', label: `Little or no data (${Math.round(coverage * 100)}% covered)` };
}

const TimeSlider: React.FC<TimeSliderProps> = ({
    minYear,
    maxYear,
    currentYear,
    onChange,
    coverageByYear = {},
}) => {
    const [hoveredYear, setHoveredYear] = useState<number | null>(null);

    const marks: number[] = [];
    for (let y = minYear; y <= maxYear; y++) {
        if (y % 5 === 0 || y === minYear || y === maxYear) {
            marks.push(y);
        }
    }

    const hoveredCoverage = hoveredYear !== null ? getCoverageClass(coverageByYear[hoveredYear]) : null;

    return (
        <div className="w-full relative px-2">
            <div className="flex justify-between items-end mb-2">
                <span className="text-2xl font-bold text-slate-200 font-mono tracking-tighter">{currentYear}</span>
                <div className="flex items-center gap-3">
                    {hoveredCoverage && hoveredYear !== null && (
                        <span className="text-[10px] text-slate-400 transition-opacity duration-200">
                            {hoveredYear}: {hoveredCoverage.label}
                        </span>
                    )}
                    <span className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold">Timeline</span>
                </div>
            </div>

            <input
                type="range"
                min={minYear}
                max={maxYear}
                value={currentYear}
                onChange={(e) => onChange(parseInt(e.target.value))}
                className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-500 hover:accent-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 transition-all"
                aria-label="Select Year"
                aria-valuemin={minYear}
                aria-valuemax={maxYear}
                aria-valuenow={currentYear}
                aria-valuetext={`Year ${currentYear}`}
            />

            {/* Coverage-Colored Ticks */}
            <div className="flex justify-between w-full mt-2 select-none">
                {marks.map(year => {
                    const { color } = getCoverageClass(
                        Object.keys(coverageByYear).length > 0 ? coverageByYear[year] : undefined
                    );
                    const isActive = year === currentYear;
                    return (
                        <div
                            key={year}
                            className="flex flex-col items-center cursor-pointer group"
                            onMouseEnter={() => setHoveredYear(year)}
                            onMouseLeave={() => setHoveredYear(null)}
                            onClick={() => onChange(year)}
                        >
                            <div
                                className={`h-2 w-1.5 rounded-sm mb-1 transition-all duration-200
                                    ${isActive ? 'bg-emerald-400 scale-125' : color}
                                    group-hover:scale-125`}
                            />
                            <span className={`text-[10px] transition-colors duration-200
                                ${isActive
                                    ? 'text-emerald-400 font-bold'
                                    : 'text-slate-600 group-hover:text-slate-400'
                                }`}
                            >
                                {year}
                            </span>
                        </div>
                    );
                })}
            </div>

            {/* Coverage Legend */}
            {Object.keys(coverageByYear).length > 0 && (
                <div className="flex items-center gap-4 mt-3 justify-end">
                    <div className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-sm bg-emerald-400" />
                        <span className="text-[9px] text-slate-500">&gt;50%</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-sm bg-amber-400" />
                        <span className="text-[9px] text-slate-500">20–50%</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-sm bg-slate-500" />
                        <span className="text-[9px] text-slate-500">&lt;20%</span>
                    </div>
                </div>
            )}
        </div>
    );
};

export default TimeSlider;

