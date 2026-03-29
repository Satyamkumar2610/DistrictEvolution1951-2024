"use client";
import { ChartSeries } from './ComparisonChart';
import { AnalysisTimelinePoint } from '../../services/api';

interface ComparisonTableProps {
    data: AnalysisTimelinePoint[];
    splitYear: number;
    series: ChartSeries[];
}

export function ComparisonTable({ data, splitYear, series }: ComparisonTableProps) {
    if (!data) return null;

    const getMetricValue = (point: AnalysisTimelinePoint, key: string) => {
        const value = point[key];
        return typeof value === 'number' ? value : null;
    };

    const rows = series.map((s: ChartSeries) => {
        const preData = data
            .filter((d) => d.year >= splitYear - 5 && d.year < splitYear)
            .map((d) => getMetricValue(d, s.id))
            .filter((value): value is number => value != null);
        const avgPre = preData.length > 0 ? preData.reduce((a: number, b: number) => a + b, 0) / preData.length : null;

        // Post-Split Window (Split to Split+5)
        const postData = data
            .filter((d) => d.year >= splitYear && d.year <= splitYear + 5)
            .map((d) => getMetricValue(d, s.id))
            .filter((value): value is number => value != null);

        const avgPost = postData.length > 0 ? postData.reduce((a: number, b: number) => a + b, 0) / postData.length : null;

        // Calculate Standard Deviation for Volatility
        const stdDevPre = preData.length > 0 ? Math.sqrt(preData.reduce((acc: number, val: number) => acc + Math.pow(val - (avgPre || 0), 2), 0) / preData.length) : null;
        const stdDevPost = postData.length > 0 ? Math.sqrt(postData.reduce((acc: number, val: number) => acc + Math.pow(val - (avgPost || 0), 2), 0) / postData.length) : null;

        const cvPre = (avgPre && avgPre !== 0 && stdDevPre !== null) ? (stdDevPre / avgPre) * 100 : null;
        const cvPost = (avgPost && avgPost !== 0 && stdDevPost !== null) ? (stdDevPost / avgPost) * 100 : null;

        let change = null;
        if (avgPre != null && avgPost != null && avgPre !== 0) {
            change = ((avgPost - avgPre) / avgPre) * 100;
        }

        return {
            entity: s.label,
            pre: avgPre,
            post: avgPost,
            cvPre,
            cvPost,
            change,
            yearsPre: preData.length,
            yearsPost: postData.length
        };
    });

    return (
        <div className="mt-6 bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
            <div className="px-4 py-2 bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-600 uppercase tracking-wider flex justify-between">
                <span>Statistical Comparison (±5 Year Window)</span>
                <span className="text-[10px] normal-case text-slate-500 hidden sm:inline">CV = Volatility (Lower is more stable)</span>
            </div>
            <table className="w-full text-xs text-left">
                <thead>
                    <tr className="border-b border-slate-200 text-slate-500 bg-white">
                        <th className="px-4 py-2 font-semibold">Entity</th>
                        <th className="px-4 py-2 text-right font-semibold">Avg (Pre-{splitYear})</th>
                        <th className="px-4 py-2 text-right font-semibold">Avg (Post-{splitYear})</th>
                        <th className="px-4 py-2 text-right font-semibold">% Change</th>
                        <th className="px-4 py-2 text-right font-semibold">Volatility (CV)</th>
                        <th className="px-4 py-2 text-center font-semibold">Confidence</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                    {rows.map((r, idx) => (
                        <tr key={idx} className="hover:bg-slate-50 transition-colors">
                            <td className="px-4 py-3 font-semibold text-slate-800">{r.entity}</td>
                            <td className="px-4 py-3 text-right text-slate-600 font-medium">
                                {r.pre !== null ? r.pre.toLocaleString(undefined, { maximumFractionDigits: 1 }) : '—'}
                            </td>
                            <td className="px-4 py-3 text-right text-slate-600 font-medium">
                                {r.post !== null ? r.post.toLocaleString(undefined, { maximumFractionDigits: 1 }) : '—'}
                            </td>
                            <td className="px-4 py-3 text-right">
                                {r.change !== null ? (
                                    <span className={`${r.change > 0 ? 'text-emerald-600' : 'text-rose-600'} font-mono font-bold`}>
                                        {r.change > 0 ? '+' : ''}{r.change.toFixed(1)}%
                                    </span>
                                ) : '—'}
                            </td>
                            <td className="px-4 py-3 text-right font-mono text-slate-600">
                                {r.cvPre !== null && r.cvPost !== null ? (
                                    <div className="flex flex-col items-end leading-none gap-0.5">
                                        <span className="text-[10px] font-medium text-slate-500">Pre: {r.cvPre.toFixed(1)}%</span>
                                        <span className={`font-semibold ${r.cvPost < r.cvPre ? 'text-emerald-600' : 'text-amber-600'}`}>Post: {r.cvPost.toFixed(1)}%</span>
                                    </div>
                                ) : '—'}
                            </td>
                            <td className="px-4 py-3 text-center">
                                {r.yearsPre >= 3 && r.yearsPost >= 3 ? (
                                    <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded text-[10px] font-bold">High</span>
                                ) : (
                                    <span className="bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded text-[10px] font-bold">Low Data</span>
                                )}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
