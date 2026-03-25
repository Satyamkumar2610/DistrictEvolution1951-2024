'use client';

import React, { useState } from 'react';
import { usePathname } from 'next/navigation';
import Sidebar from './Sidebar';
import AIAnalyst from './AIAnalyst';

export default function AppLayout({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const [isAnalystOpen, setIsAnalystOpen] = useState(false);

    const content = pathname === '/explore/map' ? (
        <>{children}</>
    ) : (
        <div className="flex h-screen bg-slate-50 overflow-hidden text-slate-900 selection:bg-indigo-100 selection:text-indigo-900">
            <Sidebar />
            <main className="flex-1 overflow-y-auto custom-scrollbar relative pt-14 md:pt-0 pb-10">
                {children}
            </main>
        </div>
    );

    return (
        <>
            {content}
            
            {/* AI Analyst Floating Action Button */}
            <button 
                onClick={() => setIsAnalystOpen((prev) => !prev)}
                className={`fixed bottom-6 right-6 p-4 rounded-full text-white shadow-xl hover:scale-105 transition-all z-50 flex items-center justify-center text-xl ${isAnalystOpen ? 'bg-slate-800' : 'bg-indigo-600 hover:bg-indigo-700'}`}
                aria-label="Toggle AI Analyst"
            >
                {isAnalystOpen ? '✕' : '✨'}
            </button>

            {/* AI Analyst Panel Overlay */}
            {isAnalystOpen && (
                <div className="fixed bottom-24 right-6 w-96 sm:w-[400px] h-[600px] max-h-[70vh] max-w-[calc(100vw-3rem)] z-50 shadow-2xl rounded-xl overflow-hidden animate-in slide-in-from-bottom-8 fade-in-20 duration-300">
                    <AIAnalyst onClose={() => setIsAnalystOpen(false)} />
                </div>
            )}
        </>
    );
}
