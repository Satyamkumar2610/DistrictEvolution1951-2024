import React from 'react';
import { Info } from 'lucide-react';

interface TooltipProps {
    text: React.ReactNode;
    children?: React.ReactNode;
    width?: string;
    position?: 'top' | 'bottom' | 'left' | 'right';
}

export default function Tooltip({ text, children, width = 'w-48', position = 'top' }: TooltipProps) {
    const positionClasses = {
        top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
        bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
        left: 'right-full top-1/2 -translate-y-1/2 mr-2',
        right: 'left-full top-1/2 -translate-y-1/2 ml-2',
    };

    const arrowPosition = {
        top: 'top-full left-1/2 -translate-x-1/2 border-t-slate-800 border-x-transparent border-b-transparent',
        bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-slate-800 border-x-transparent border-t-transparent',
        left: 'left-full top-1/2 -translate-y-1/2 border-l-slate-800 border-y-transparent border-r-transparent',
        right: 'right-full top-1/2 -translate-y-1/2 border-r-slate-800 border-y-transparent border-l-transparent',
    };

    return (
        <span className="group/tooltip relative inline-flex items-center cursor-help">
            {children || <Info size={14} className="text-slate-400 hover:text-slate-600 transition-colors inline-block ml-1" />}
            
            <div className={`absolute ${positionClasses[position]} ${width} bg-slate-800 text-slate-100 text-[10px] p-2 rounded shadow-lg opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all duration-200 z-50 pointer-events-none font-normal normal-case break-words leading-tight tracking-normal`}>
                {text}
                <div className={`absolute w-0 h-0 border-[5px] ${arrowPosition[position]}`} />
            </div>
        </span>
    );
}
