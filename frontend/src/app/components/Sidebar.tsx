'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import {
    Map, Shield, GitBranch, Wheat, FileText, BookOpen, Menu, X,
    Layers, Droplet, Network, Target, Home, BarChart3, Globe2, Database,
    Activity, CloudLightning, TrendingUp, CheckCircle, Scissors
} from 'lucide-react';
import { buildPublicOriginUrl } from '../services/api/config';

const NAV_GROUPS = [
    {
        name: "Overview",
        items: [
            { href: '/', label: 'Dashboard', icon: Home },
            { href: '/dashboard/split-impact', label: 'Split Impact', icon: Scissors },
            { href: '/explore/map', label: 'Interactive Map', icon: Map },
            { href: '/compare', label: 'District Comparison', icon: BarChart3 },
        ]
    },
    {
        name: "Analytics",
        items: [
            { href: '/analytics/crop-portfolio', label: 'Crop Portfolio', icon: Wheat },
            { href: '/analytics/crop-shift', label: 'Crop Shift', icon: Layers },
            { href: '/analytics/yield-gap', label: 'Yield Gap', icon: Target },
            { href: '/analytics/water-stress', label: 'Water Stress', icon: Droplet },
            { href: '/analytics/spatial-contagion', label: 'Spatial Contagion', icon: Network },
            { href: '/analytics/risk-monitor', label: 'Risk Monitor', icon: Shield },
            { href: '/analytics/anomaly-scan', label: 'Anomaly Scan', icon: Activity },
            { href: '/analytics/climate-shocks', label: 'Climate Shocks', icon: CloudLightning },
            { href: '/analytics/forecast-validation', label: 'Forecast Validation', icon: CheckCircle },
            { href: '/analytics/resilience-composite', label: 'Resilience', icon: Shield },
            { href: '/analytics/yield-frontier', label: 'Yield Frontier', icon: TrendingUp },
            { href: '/visualise', label: 'Data Visualiser', icon: BarChart3 },
        ]
    },
    {
        name: "Lineage & Boundary",
        items: [
            { href: '/lineage/graph', label: 'Lineage Graph', icon: GitBranch },
            { href: '/lineage/split-report', label: 'Split Report', icon: GitBranch },
            { href: '/lineage/state-overview', label: 'State Overview', icon: Globe2 },
            { href: '/split-analyzer', label: 'Split Analyzer', icon: Shield },
            { href: '/reconstructor', label: 'Lineage Reconstructor', icon: Layers },
            { href: '/data-quality', label: 'Data Quality', icon: Database },
        ]
    },
    {
        name: "Resources",
        items: [
            { href: '/reports', label: 'Reports', icon: FileText },
            { href: '/methodology', label: 'Methodology', icon: BookOpen },
        ]
    }
];

export default function Sidebar() {
    const pathname = usePathname();
    const [mobileOpen, setMobileOpen] = useState(false);
    const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

    useEffect(() => {
        fetch(buildPublicOriginUrl('/health'), { signal: AbortSignal.timeout(5000) })
            .then(r => setBackendOnline(r.ok))
            .catch(() => setBackendOnline(false));
    }, []);

    const isActive = (href: string) => {
        if (href === '/') return pathname === '/';
        return pathname === href || pathname.startsWith(href + '/');
    };

    return (
        <>
            {/* Mobile Toggle Button (Top Bar on Mobile) */}
            <div className="md:hidden fixed top-0 left-0 w-full h-14 bg-slate-900 z-50 flex items-center justify-between px-4 border-b border-slate-800">
                <div className="flex items-center gap-2">
                    <Image src="/logo.png" alt="I-ASCAP" width={32} height={32} className="rounded-lg" />
                    <span className="font-bold text-white tracking-wide">I-ASCAP</span>
                </div>
                <button
                    onClick={() => setMobileOpen(!mobileOpen)}
                    className="p-2 text-slate-400 hover:text-white rounded-lg transition focus:outline-none"
                >
                    {mobileOpen ? <X size={20} /> : <Menu size={20} />}
                </button>
            </div>

            {/* Sidebar Desktop + Mobile Drawer */}
            <aside className={`
                fixed md:static inset-y-0 left-0 z-40
                w-64 bg-slate-900 border-r border-slate-800 text-slate-300
                transform transition-transform duration-300 ease-in-out
                flex flex-col shadow-2xl md:shadow-none
                ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
            `}>
                <div className="hidden md:flex h-16 shrink-0 items-center justify-center gap-3 px-6 border-b border-slate-800/50 bg-slate-900/50 backdrop-blur-md">
                    <Image src="/logo.png" alt="I-ASCAP" width={32} height={32} className="rounded-lg" />
                    <span className="font-bold text-white tracking-wide text-sm">I-ASCAP Platform</span>
                </div>

                <div className="flex-1 overflow-y-auto custom-scrollbar py-6 px-4 pb-20 md:pb-6 mt-14 md:mt-0">
                    {NAV_GROUPS.map((group) => (
                        <div key={group.name} className="mb-8">
                            <h3 className="px-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-2">
                                {group.name}
                            </h3>
                            <div className="space-y-1">
                                {group.items.map((route) => {
                                    const active = isActive(route.href);
                                    const Icon = route.icon;
                                    return (
                                        <Link
                                            key={route.href}
                                            href={route.href}
                                            onClick={() => setMobileOpen(false)}
                                            className={`
                                                flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition-all duration-200 group
                                                ${active
                                                    ? 'bg-indigo-500/10 text-indigo-400 font-bold border border-indigo-500/20 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]'
                                                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/50 hover:border-slate-700/50 border border-transparent'
                                                }
                                            `}
                                        >
                                            <Icon size={16} className={`transition-colors ${active ? "text-indigo-400" : "text-slate-500 group-hover:text-slate-300"}`} />
                                            {route.label}
                                        </Link>
                                    );
                                })}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Dynamic System Status */}
                <div className="p-4 border-t border-slate-800/50 bg-slate-900/50 backdrop-blur-sm shrink-0">
                    <div className="bg-slate-800/50 rounded-xl p-3 border border-slate-700/50 flex flex-col items-center text-center">
                        <span className="text-[10px] uppercase font-bold text-slate-500 mb-1">Backend Status</span>
                        <div className="flex items-center gap-2">
                            <span className="relative flex h-2 w-2">
                                {backendOnline && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>}
                                <span className={`relative inline-flex rounded-full h-2 w-2 ${backendOnline === true ? 'bg-emerald-500' : backendOnline === false ? 'bg-rose-500' : 'bg-slate-500'}`}></span>
                            </span>
                            <span className="text-[11px] font-medium text-slate-300">
                                {backendOnline === true ? 'Online' : backendOnline === false ? 'Offline' : 'Checking...'}
                            </span>
                        </div>
                    </div>
                </div>
            </aside>

            {/* Backdrop for mobile */}
            {mobileOpen && (
                <div
                    className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-30 md:hidden animate-in fade-in"
                    onClick={() => setMobileOpen(false)}
                />
            )}
        </>
    );
}
