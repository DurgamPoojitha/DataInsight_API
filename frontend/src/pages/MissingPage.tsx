import React from 'react';
import { useParams } from 'react-router-dom';
import { useDatasetMissing } from '../hooks/useApi';
import { Loader2, AlertCircle, XCircle } from 'lucide-react';
import { motion } from 'framer-motion';

export const MissingPage: React.FC = () => {
  const { datasetId } = useParams<{ datasetId: string }>();
  const { data: missing, isLoading, error } = useDatasetMissing(datasetId!);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !missing) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-destructive">
        <AlertCircle className="h-16 w-16 mb-4" />
        <h2 className="text-2xl font-bold">Failed to load missing values</h2>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 pb-20">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Missing Values Analysis</h1>
        <p className="text-muted-foreground">Detection and quantification of null or empty cells.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-4">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-6 flex flex-col gap-2 border-destructive/30">
          <div className="flex items-center gap-2 text-destructive mb-2">
            <XCircle className="h-5 w-5" />
            <h3 className="font-semibold">Total Missing Cells</h3>
          </div>
          <span className="text-4xl font-bold text-destructive">{missing.summary.total_missing_cells}</span>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass-card p-6 flex flex-col gap-2">
          <h3 className="font-semibold text-muted-foreground mb-2">Overall Missing Percentage</h3>
          <span className="text-4xl font-bold">{missing.summary.overall_missing_pct.toFixed(2)}%</span>
        </motion.div>
      </div>

      <h2 className="text-2xl font-semibold mt-4">Columns with Missing Data</h2>
      <div className="grid grid-cols-1 gap-4">
        {missing.affected_columns?.map((colInfo: any, index: number) => {
          if (colInfo.missing_count === 0) return null;
          return (
            <motion.div
              key={colInfo.column}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 + index * 0.05 }}
              className="glass-card p-4 flex items-center bg-white/5"
            >
              <div className="w-1/3 font-medium text-lg truncate pr-4">{colInfo.column}</div>
              <div className="w-2/3 flex items-center gap-4">
                <div className="flex-1 h-3 bg-white/10 rounded-full overflow-hidden">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.min(100, (colInfo.missing_count / missing.summary.total_missing_cells) * 100)}%` }}
                    transition={{ duration: 1, delay: 0.5 + index * 0.1 }}
                    className="h-full bg-destructive"
                  />
                </div>
                <span className="w-16 text-right font-bold text-destructive">{colInfo.missing_count}</span>
              </div>
            </motion.div>
          );
        })}
        
        {missing.summary.total_missing_cells === 0 && (
          <div className="p-8 text-center glass-card border-emerald-500/30">
            <p className="text-xl font-medium text-emerald-400">Perfect! No missing values detected in this dataset.</p>
          </div>
        )}
      </div>
    </div>
  );
};
