import React from 'react';
import { useParams } from 'react-router-dom';
import { useDatasetStatistics } from '../hooks/useApi';
import { AlertCircle, BarChart, Hash, ArrowDownUp } from 'lucide-react';
import { motion } from 'framer-motion';

export const StatisticsPage: React.FC = () => {
  const { datasetId } = useParams<{ datasetId: string }>();
  const { data: stats, isLoading, error } = useDatasetStatistics(datasetId!);

  if (isLoading) {
    return (
      <div className="flex h-full w-full flex-col gap-4 p-4">
        {/* Skeleton layout for premium feel */}
        <div className="h-10 w-64 bg-muted rounded-md animate-pulse"></div>
        <div className="h-4 w-96 bg-muted/50 rounded-md animate-pulse mb-8"></div>
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <div className="h-12 w-full bg-muted/30 border-b border-border animate-pulse"></div>
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="h-16 w-full border-b border-border/50 animate-pulse bg-card"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-destructive min-h-[500px]">
        <AlertCircle className="h-12 w-12 mb-4 opacity-80" />
        <h2 className="text-xl font-semibold">Failed to load statistics</h2>
      </div>
    );
  }

  const columns = Object.entries(stats.columns || {});

  return (
    <div className="flex flex-col gap-8 pb-20 max-w-[1600px] mx-auto w-full pt-4">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
            <BarChart className="h-5 w-5 text-primary" />
          </div>
          Statistical Analysis
        </h1>
        <p className="text-muted-foreground text-sm font-medium ml-14">Comprehensive descriptive statistics and distributions.</p>
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
        <div className="overflow-x-auto custom-scrollbar">
          <table className="w-full text-sm text-left border-collapse">
            <thead className="bg-muted/30 border-b border-border">
              <tr>
                <th className="px-6 py-4 font-semibold text-muted-foreground whitespace-nowrap sticky left-0 bg-muted/80 backdrop-blur-md z-10 w-64 border-r border-border flex items-center gap-2">
                  <Hash className="h-4 w-4" /> Feature Name
                </th>
                <th className="px-6 py-4 font-semibold text-muted-foreground whitespace-nowrap"><div className="flex items-center gap-1.5 cursor-pointer hover:text-foreground">Mean <ArrowDownUp className="h-3 w-3"/></div></th>
                <th className="px-6 py-4 font-semibold text-muted-foreground whitespace-nowrap"><div className="flex items-center gap-1.5 cursor-pointer hover:text-foreground">Median <ArrowDownUp className="h-3 w-3"/></div></th>
                <th className="px-6 py-4 font-semibold text-muted-foreground whitespace-nowrap"><div className="flex items-center gap-1.5 cursor-pointer hover:text-foreground">Min <ArrowDownUp className="h-3 w-3"/></div></th>
                <th className="px-6 py-4 font-semibold text-muted-foreground whitespace-nowrap"><div className="flex items-center gap-1.5 cursor-pointer hover:text-foreground">Max <ArrowDownUp className="h-3 w-3"/></div></th>
                <th className="px-6 py-4 font-semibold text-muted-foreground whitespace-nowrap">Std Dev</th>
                <th className="px-6 py-4 font-semibold text-muted-foreground whitespace-nowrap">Skewness</th>
                <th className="px-6 py-4 font-semibold text-muted-foreground whitespace-nowrap">Missing %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {columns.map(([columnName, data]: [string, any], index) => (
                <motion.tr 
                  key={columnName}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="hover:bg-muted/20 transition-colors group"
                >
                  <td className="px-6 py-4 font-medium text-foreground sticky left-0 bg-card group-hover:bg-muted/20 transition-colors border-r border-border whitespace-nowrap w-64 z-10 shadow-[1px_0_0_0_rgba(255,255,255,0.05)]">
                    {columnName}
                  </td>
                  <td className="px-6 py-4 text-foreground/80 font-mono text-xs">{formatValue(data.mean)}</td>
                  <td className="px-6 py-4 text-foreground/80 font-mono text-xs">{formatValue(data.median)}</td>
                  <td className="px-6 py-4 text-foreground/80 font-mono text-xs">{formatValue(data.minimum)}</td>
                  <td className="px-6 py-4 text-foreground/80 font-mono text-xs">{formatValue(data.maximum)}</td>
                  <td className="px-6 py-4 text-foreground/80 font-mono text-xs">{formatValue(data.std_dev)}</td>
                  <td className="px-6 py-4 text-foreground/80 font-mono text-xs">{formatValue(data.distribution?.skewness)}</td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <span className="text-foreground/80 font-mono text-xs">{formatValue(data.nan_pct)}%</span>
                      <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full ${Number(data.nan_pct) > 10 ? 'bg-destructive' : 'bg-primary'}`} 
                          style={{ width: `${Math.min(100, Number(data.nan_pct || 0))}%` }} 
                        />
                      </div>
                    </div>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

function formatValue(value: any): string {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'number') {
    // If it's an integer, don't show decimals
    if (Number.isInteger(value)) return value.toString();
    // Otherwise limit to 4 decimals max, strip trailing zeros
    return parseFloat(value.toFixed(4)).toString();
  }
  return String(value);
}
