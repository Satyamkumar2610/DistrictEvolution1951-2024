"use client";

import React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import {
    Map, GitBranch, Wheat, Layers, Droplet, Network, Target, Shield,
    ArrowRight, BarChart3, Database, Globe2, TrendingUp
} from 'lucide-react';

const FEATURE_SECTIONS = [
    {
        title: "Explore",
        description: "Visualize agricultural patterns across India's districts",
        color: "emerald",
        items: [
            {
                href: '/explore/map',
                icon: Map,
                title: 'Interactive Map',
                description: 'Choropleth map with time slider, crop/metric overlays, and district drill-down',
            },
            {
                href: '/compare',
                icon: BarChart3,
                title: 'District Comparison',
                description: 'Side-by-side yield, area, and production comparison across districts',
            },
        ],
    },
    {
        title: "Analytics",
        description: "Deep-dive into agricultural performance metrics",
        color: "indigo",
        items: [
            {
                href: '/analytics/crop-portfolio',
                icon: Wheat,
                title: 'Crop Portfolio',
                description: 'Diversification indices, yield trends, and crop-correlation matrices',
            },
            {
                href: '/analytics/crop-shift',
                icon: Layers,
                title: 'Crop Shift',
                description: 'Track how crop composition changes over time within districts',
            },
            {
                href: '/analytics/yield-gap',
                icon: Target,
                title: 'Yield Gap',
                description: 'Frontier analysis showing convergence/divergence across districts',
            },
            {
                href: '/analytics/water-stress',
                icon: Droplet,
                title: 'Water Stress',
                description: 'Mismatch index mapping water-intensive crops against rainfall',
            },
            {
                href: '/analytics/spatial-contagion',
                icon: Network,
                title: 'Spatial Contagion',
                description: 'Spillover effects and regional growth patterns between neighbors',
            },
            {
                href: '/analytics/risk-monitor',
                icon: Shield,
                title: 'Risk Monitor',
                description: 'High-risk district monitoring with anomaly detection',
            },
        ],
    },
    {
        title: "Lineage & Boundary",
        description: "Track district splits, merges, and their impact on data continuity",
        color: "violet",
        items: [
            {
                href: '/lineage/graph',
                icon: GitBranch,
                title: 'Lineage Graph',
                description: 'Visual lineage tree of district boundary changes since 1951',
            },
            {
                href: '/lineage/split-report',
                icon: GitBranch,
                title: 'Split Impact Report',
                description: 'Before/after analysis of agricultural yields around split events',
            },
            {
                href: '/lineage/state-overview',
                icon: Globe2,
                title: 'State Overview',
                description: 'State-level summaries with top/bottom performer rankings',
            },
        ],
    },
];

const STATS = [
    { label: 'Districts', value: '928+', icon: Database },
    { label: 'Metrics', value: '1M+', icon: BarChart3 },
    { label: 'Boundary Changes', value: '399', icon: GitBranch },
    { label: 'Years Covered', value: '1966–2017', icon: TrendingUp },
];

const colorMap: Record<string, { bg: string; border: string; text: string; badge: string; hover: string }> = {
    emerald: {
        bg: 'bg-emerald-50/50', border: 'border-emerald-200', text: 'text-emerald-700',
        badge: 'bg-emerald-100 text-emerald-700', hover: 'hover:border-emerald-300 hover:shadow-emerald-100/50',
    },
    indigo: {
        bg: 'bg-indigo-50/50', border: 'border-indigo-200', text: 'text-indigo-700',
        badge: 'bg-indigo-100 text-indigo-700', hover: 'hover:border-indigo-300 hover:shadow-indigo-100/50',
    },
    violet: {
        bg: 'bg-violet-50/50', border: 'border-violet-200', text: 'text-violet-700',
        badge: 'bg-violet-100 text-violet-700', hover: 'hover:border-violet-300 hover:shadow-violet-100/50',
    },
};

export default function LandingDashboard() {
    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-50">
            {/* Hero */}
            <header className="px-6 md:px-10 pt-10 pb-8">
                <div className="max-w-6xl mx-auto">
                    <div className="flex items-center gap-3 mb-2">
                        <Image src="/logo.png" alt="I-ASCAP" width={44} height={44} className="rounded-xl shadow-lg shadow-indigo-200" />
                        <span className="text-xs font-mono text-slate-400 uppercase tracking-widest">v1.0</span>
                    </div>
                    <h1 className="text-3xl md:text-4xl font-bold text-slate-900 tracking-tight mt-4">
                        Indian Agri-Spatial Comparative Analytics
                    </h1>
                    <p className="text-slate-500 text-base md:text-lg mt-2 max-w-2xl leading-relaxed">
                        Research-grade infrastructure for longitudinal analysis of agricultural performance across
                        district boundary evolution in India (1966–2024).
                    </p>

                    {/* Quick Stats */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-8">
                        {STATS.map((stat) => {
                            const Icon = stat.icon;
                            return (
                                <div key={stat.label} className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                                    <div className="flex items-center gap-2 mb-1">
                                        <Icon size={14} className="text-slate-400" />
                                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{stat.label}</span>
                                    </div>
                                    <div className="text-xl font-bold text-slate-900 font-mono">{stat.value}</div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </header>

            {/* Feature Sections */}
            <section className="px-6 md:px-10 pb-16">
                <div className="max-w-6xl mx-auto space-y-10">
                    {FEATURE_SECTIONS.map((section) => {
                        const colors = colorMap[section.color];
                        return (
                            <div key={section.title}>
                                <div className="flex items-center gap-3 mb-4">
                                    <span className={`text-xs font-bold uppercase tracking-widest px-2.5 py-1 rounded-lg ${colors.badge}`}>
                                        {section.title}
                                    </span>
                                    <span className="text-xs text-slate-400">{section.description}</span>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {section.items.map((item) => {
                                        const Icon = item.icon;
                                        return (
                                            <Link
                                                key={item.href}
                                                href={item.href}
                                                className={`group block p-5 bg-white border ${colors.border} rounded-xl shadow-sm transition-all duration-200 ${colors.hover} hover:shadow-md`}
                                            >
                                                <div className="flex items-start justify-between mb-3">
                                                    <div className={`w-9 h-9 rounded-lg ${colors.bg} flex items-center justify-center`}>
                                                        <Icon size={18} className={colors.text} />
                                                    </div>
                                                    <ArrowRight size={14} className="text-slate-300 group-hover:text-slate-500 transition-colors mt-1" />
                                                </div>
                                                <h3 className="font-bold text-slate-900 text-sm mb-1">{item.title}</h3>
                                                <p className="text-slate-500 text-xs leading-relaxed">{item.description}</p>
                                            </Link>
                                        );
                                    })}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </section>

            {/* Footer */}
            <footer className="border-t border-slate-200 bg-slate-50 px-6 md:px-10 py-8">
                <div className="max-w-6xl mx-auto">
                    <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                        {/* Left: Brand + Description */}
                        <div className="flex flex-col items-center md:items-start gap-2">
                            <div className="flex items-center gap-2">
                                <Image src="/logo.png" alt="I-ASCAP" width={28} height={28} className="rounded-lg" />
                                <span className="font-bold text-slate-700 text-sm">I-ASCAP Platform</span>
                            </div>
                            <p className="text-xs text-slate-400 max-w-sm text-center md:text-left">
                                Indian Agri-Spatial Comparative Analytics Platform — Research-grade infrastructure for longitudinal agricultural analysis.
                            </p>
                        </div>

                        {/* Center: Navigation */}
                        <div className="flex items-center gap-6 text-xs text-slate-400">
                            <Link href="/methodology" className="hover:text-indigo-600 transition-colors">Methodology</Link>
                            <Link href="/reports" className="hover:text-indigo-600 transition-colors">Reports</Link>
                            <Link href="/explore/map" className="hover:text-indigo-600 transition-colors">Explore Map</Link>
                        </div>

                        {/* Right: GitHub */}
                        <div className="flex items-center gap-3">
                            <a
                                href="https://github.com/Satyamkumar2610/I-ASCAP"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 text-white text-xs font-medium hover:bg-slate-800 transition-colors"
                            >
                                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" /></svg>
                                Source Code
                            </a>
                            <a
                                href="https://github.com/Satyamkumar2610"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-slate-400 hover:text-indigo-600 transition-colors"
                            >
                                @Satyamkumar2610
                            </a>
                        </div>
                    </div>

                    {/* Bottom bar */}
                    <div className="mt-6 pt-4 border-t border-slate-200 flex flex-col md:flex-row items-center justify-between gap-2">
                        <div className="flex items-center gap-2 text-[11px] text-slate-400">
                            <Database size={11} />
                            <span>Dataset v1.5 Harmonized · Boundary v2024-01-15</span>
                        </div>
                        <span className="text-[11px] text-slate-400">© 2026 Satyam Kumar. All rights reserved.</span>
                    </div>
                </div>
            </footer>
        </div>
    );
}
