import React from 'react';
import { useParams } from 'react-router-dom';
import { useDatasetOutliers } from '../hooks/useApi';
import { Loader2, AlertCircle, AlertTriangle } from 'lucide-react';
import { motion } from 'framer-motion';

export const OutliersPage: React.FC = () => {
  const { datasetId } = useParams<{ datasetId: string }>();
  const { data: outliers, isLoading, error } = useDatasetOutliers(datasetId!);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !outliers) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-destructive">
        <AlertCircle className="h-16 w-16 mb-4" />
        <h2 className="text-2xl font-bold">Failed to load outliers</h2>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 pb-20">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Outlier Detection</h1>
        <p className="text-muted-foreground">Anomalies detected using statistical boundaries.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-4">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-6 flex flex-col gap-2 border-amber-500/30">
          <div className="flex items-center gap-2 text-amber-400 mb-2">
            <AlertTriangle className="h-5 w-5" />
            <h3 className="font-semibold">Total Outliers</h3>
          </div>
          <span className="text-4xl font-bold text-amber-400">{outliers.total_outlier_cells}</span>
          <p className="text-sm text-muted-foreground">Across all numeric columns</p>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass-card p-6 flex flex-col gap-2">
          <h3 className="font-semibold text-muted-foreground mb-2">Affected Rows</h3>
          <span className="text-4xl font-bold">{outliers.total_outlier_rows}</span>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass-card p-6 flex flex-col gap-2">
          <h3 className="font-semibold text-muted-foreground mb-2">Method Used</h3>
          <span className="text-4xl font-bold text-primary capitalize">{outliers.method}</span>
        </motion.div>
      </div>

      <h2 className="text-2xl font-semibold mt-4">Column Breakdown</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {Object.entries(outliers.column_results || {}).map(([col, result]: [string, any], index) => {
          if (result.outlier_count === 0) return null;
          return (
            <motion.div
              key={col}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.3 + index * 0.05 }}
              className="glass-card p-6 flex justify-between items-center bg-white/5 hover:bg-white/10 transition-colors"
            >
              <span className="text-lg font-medium">{col}</span>
              <div className="flex items-center gap-3">
                <span className="text-2xl font-bold text-amber-400">{result.outlier_count}</span>
                <span className="text-sm text-muted-foreground">detected</span>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};
