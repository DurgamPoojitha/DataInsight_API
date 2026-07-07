import React from 'react';
import { useParams } from 'react-router-dom';
import { useDatasetMissing } from '../hooks/useApi';
import { AlertCircle, XCircle, SearchX, CheckCircle2 } from 'lucide-react';
import { motion } from 'framer-motion';

export const MissingPage: React.FC = () => {
  const { datasetId } = useParams<{ datasetId: string }>();
  const { data: missing, isLoading, error } = useDatasetMissing(datasetId!);

  if (isLoading) {
    return (
      <div className="flex h-full w-full flex-col gap-6 p-4 max-w-[1400px] mx-auto">
        <div className="h-10 w-64 bg-muted rounded-md animate-pulse"></div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="h-32 w-full bg-card border border-border rounded-xl animate-pulse"></div>
          <div className="h-32 w-full bg-card border border-border rounded-xl animate-pulse"></div>
        </div>
        <div className="h-[400px] w-full bg-card border border-border rounded-xl animate-pulse"></div>
      </div>
    );
  }

  if (error || !missing) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-destructive min-h-[500px]">
        <AlertCircle className="h-12 w-12 mb-4 opacity-80" />
        <h2 className="text-xl font-semibold">Failed to load missing values</h2>
      </div>
    );
  }

  const hasMissing = missing.summary.total_missing_cells > 0;
  const missingCols = (missing.affected_columns || []).filter((c: any) => c.missing_count > 0);

  return (
    <div className="flex flex-col gap-8 pb-20 max-w-[1400px] mx-auto w-full pt-4">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
            <SearchX className="h-5 w-5 text-primary" />
          </div>
          Missing Values Analysis
        </h1>
        <p className="text-muted-foreground text-sm font-medium ml-14">Detection and quantification of null or empty cells across features.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className={`rounded-xl border p-6 flex flex-col gap-2 ${hasMissing ? 'border-destructive/30 bg-destructive/5' : 'border-border bg-card'}`}>
          <div className="flex items-center gap-2 mb-2">
            {hasMissing ? <XCircle className="h-4 w-4 text-destructive" /> : <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Total Missing Cells</h3>
          </div>
          <span className={`text-4xl font-bold tracking-tight ${hasMissing ? 'text-destructive' : 'text-foreground'}`}>
            {missing.summary.total_missing_cells.toLocaleString()}
          </span>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="rounded-xl border border-border bg-card p-6 flex flex-col gap-2">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Overall Sparsity</h3>
          </div>
          <span className="text-4xl font-bold tracking-tight text-foreground">
            {missing.summary.overall_missing_pct.toFixed(2)}%
          </span>
        </motion.div>
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm flex flex-col">
        <div className="p-6 border-b border-border/50">
          <h2 className="text-lg font-semibold tracking-tight text-foreground">Affected Features</h2>
        </div>
        <div className="p-6 flex flex-col gap-1">
          {missingCols.map((colInfo: any, index: number) => (
            <motion.div
              key={colInfo.column}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 + index * 0.05 }}
              className="flex items-center group py-3 border-b border-border/30 last:border-0"
            >
              <div className="w-1/3 md:w-1/4 font-medium text-sm text-foreground truncate pr-4">{colInfo.column}</div>
              <div className="w-2/3 md:w-3/4 flex items-center gap-4">
                <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.min(100, (colInfo.missing_count / missing.summary.total_missing_cells) * 100)}%` }}
                    transition={{ duration: 1, delay: 0.4 + index * 0.1, ease: "easeOut" }}
                    className="h-full bg-destructive"
                  />
                </div>
                <span className="w-20 text-right font-mono text-sm font-semibold text-destructive">{colInfo.missing_count.toLocaleString()}</span>
              </div>
            </motion.div>
          ))}
          
          {!hasMissing && (
            <div className="py-12 flex flex-col items-center justify-center text-center">
              <CheckCircle2 className="h-12 w-12 text-emerald-500/50 mb-4" />
              <p className="text-lg font-medium text-foreground">Perfect Data Quality</p>
              <p className="text-sm text-muted-foreground mt-1">No missing values were detected in any column of this dataset.</p>
            </div>
          )}
        </div>
      </div>
      
      {/* If there's an image from backend, render it elegantly full width */}
      {missing.image && (
        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="rounded-xl border border-border bg-card p-2 shadow-sm overflow-hidden"
        >
          <img src={`data:image/png;base64,${missing.image}`} alt="Missing values chart" className="w-full h-auto object-contain rounded-lg" />
        </motion.div>
      )}
    </div>
  );
};
