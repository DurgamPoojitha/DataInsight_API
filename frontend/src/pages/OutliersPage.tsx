import React from 'react';
import { useParams } from 'react-router-dom';
import { useDatasetOutliers } from '../hooks/useApi';
import { AlertCircle, AlertTriangle, Target, Activity } from 'lucide-react';
import { motion } from 'framer-motion';

export const OutliersPage: React.FC = () => {
  const { datasetId } = useParams<{ datasetId: string }>();
  const { data: outliers, isLoading, error } = useDatasetOutliers(datasetId!);

  if (isLoading) {
    return (
      <div className="flex h-full w-full flex-col gap-6 p-4 max-w-[1400px] mx-auto">
        <div className="h-10 w-64 bg-muted rounded-md animate-pulse"></div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => <div key={i} className="h-32 w-full bg-card border border-border rounded-xl animate-pulse"></div>)}
        </div>
        <div className="h-[400px] w-full bg-card border border-border rounded-xl animate-pulse mt-4"></div>
      </div>
    );
  }

  if (error || !outliers) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-destructive min-h-[500px]">
        <AlertCircle className="h-12 w-12 mb-4 opacity-80" />
        <h2 className="text-xl font-semibold">Failed to load outlier analysis</h2>
      </div>
    );
  }

  const columnsWithOutliers = Object.entries(outliers.column_results || {}).filter(([_, res]: any) => res.outlier_count > 0);

  return (
    <div className="flex flex-col gap-8 pb-20 max-w-[1400px] mx-auto w-full pt-4">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
            <Target className="h-5 w-5 text-primary" />
          </div>
          Outlier Detection
        </h1>
        <p className="text-muted-foreground text-sm font-medium ml-14">Identification of statistical anomalies across all numeric features.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-6 flex flex-col gap-2">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Total Anomalies</h3>
          </div>
          <span className="text-4xl font-bold tracking-tight text-amber-500">{outliers.total_outlier_cells.toLocaleString()}</span>
          <p className="text-xs text-muted-foreground mt-1">Across {columnsWithOutliers.length} affected columns</p>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="rounded-xl border border-border bg-card p-6 flex flex-col gap-2">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Impacted Rows</h3>
          </div>
          <span className="text-4xl font-bold tracking-tight text-foreground">{outliers.total_outlier_rows.toLocaleString()}</span>
          <p className="text-xs text-muted-foreground mt-1">Rows containing at least one outlier</p>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="rounded-xl border border-border bg-card p-6 flex flex-col gap-2 justify-between">
          <div className="flex flex-col gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Detection Method</h3>
            <span className="text-2xl font-bold tracking-tight text-foreground capitalize">{outliers.method === 'iqr' ? 'Interquartile Range (IQR)' : outliers.method}</span>
          </div>
          <div className="bg-muted px-3 py-1.5 rounded-md self-start border border-border/50">
            <span className="text-xs font-mono text-muted-foreground">Threshold: Auto</span>
          </div>
        </motion.div>
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm flex flex-col">
        <div className="p-6 border-b border-border/50 flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight text-foreground">Feature Breakdown</h2>
          <span className="text-xs font-medium text-muted-foreground bg-muted px-2 py-1 rounded">Sorted by severity</span>
        </div>
        
        <div className="p-0">
          {columnsWithOutliers.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-0">
              {columnsWithOutliers.sort((a: any, b: any) => b[1].outlier_count - a[1].outlier_count).map(([col, result]: [string, any], index) => (
                <motion.div
                  key={col}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.3 + index * 0.05 }}
                  className="p-6 border-b border-r border-border/50 flex flex-col gap-4 hover:bg-muted/10 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <span className="text-base font-semibold text-foreground truncate pr-4">{col}</span>
                    <div className="flex items-baseline gap-1 bg-amber-500/10 text-amber-500 px-2 py-0.5 rounded text-xs font-bold border border-amber-500/20">
                      {result.outlier_count}
                    </div>
                  </div>
                  
                  {outliers.boxplots && outliers.boxplots[col] ? (
                    <div className="mt-2 rounded-lg border border-border/50 bg-background overflow-hidden p-1 h-32 flex items-center justify-center">
                      <img src={`data:image/png;base64,${outliers.boxplots[col]}`} alt={`Boxplot for ${col}`} className="max-h-full max-w-full object-contain mix-blend-screen" />
                    </div>
                  ) : (
                    <div className="h-8 flex items-end">
                      <div className="w-full bg-muted h-1.5 rounded-full overflow-hidden">
                        <div className="h-full bg-amber-500" style={{ width: `${Math.min(100, (result.outlier_count / outliers.total_outlier_cells) * 100)}%` }} />
                      </div>
                    </div>
                  )}
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="py-16 flex flex-col items-center justify-center text-center">
              <AlertCircle className="h-12 w-12 text-muted-foreground/50 mb-4" />
              <p className="text-lg font-medium text-foreground">No Outliers Detected</p>
              <p className="text-sm text-muted-foreground mt-1">All numeric values fall within the expected statistical boundaries.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
