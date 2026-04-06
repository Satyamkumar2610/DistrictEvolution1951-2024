import React from 'react';

interface MSPBadgeProps {
    status: 'Above MSP' | 'At MSP' | 'Below MSP';
}

export default function MSPBadge({ status }: MSPBadgeProps) {
    if (status === 'Above MSP') {
        return (
            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                Above MSP
            </span>
        );
    }
    
    if (status === 'Below MSP') {
        return (
            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                Below MSP
            </span>
        );
    }
    
    return (
        <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
            At MSP
        </span>
    );
}
