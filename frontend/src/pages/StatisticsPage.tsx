import React from 'react';
import { useParams } from 'react-router-dom';
import { useDatasetStatistics } from '../hooks/useApi';
import { Loader2, AlertCircle, BarChart, ChevronDown } from 'lucide-react';
import { motion } from 'framer-motion';

export const StatisticsPage: React.FC = () => {
  const { datasetId } = useParams<{ datasetId: string }>();
  const { data: stats, isLoading, error } = useDatasetStatistics(datasetId!);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-destructive">
        <AlertCircle className="h-16 w-16 mb-4" />
        <h2 className="text-2xl font-bold">Failed to load statistics</h2>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 pb-20">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Statistical Analysis</h1>
        <p className="text-muted-foreground">Comprehensive statistical profiles for all numeric columns.</p>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {Object.entries(stats.columns || {}).map(([column, data]: [string, any], index) => (
          <motion.div
            key={column}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="glass-card overflow-hidden group"
          >
            <div className="p-6 border-b border-white/10 flex items-center justify-between bg-white/5">
              <div className="flex items-center gap-4">
                <div className="h-10 w-10 rounded-lg bg-primary/20 flex items-center justify-center text-primary">
                  <BarChart className="h-5 w-5" />
                </div>
                <h3 className="text-xl font-bold">{column}</h3>
              </div>
              <ChevronDown className="h-5 w-5 text-muted-foreground group-hover:text-white transition-colors" />
            </div>
            
            <div className="p-6 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              <StatItem label="Mean" value={data.mean} />
              <StatItem label="Median" value={data.median} />
              <StatItem label="Min" value={data.minimum} />
              <StatItem label="Max" value={data.maximum} />
              <StatItem label="Std Dev" value={data.std_dev} />
              <StatItem label="Variance" value={data.variance} />
              <StatItem label="Skewness" value={data.distribution?.skewness} />
              <StatItem label="Kurtosis" value={data.distribution?.kurtosis} />
              <StatItem label="Missing %" value={data.nan_pct} />
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

const StatItem = ({ label, value }: { label: string, value: any }) => {
  const displayValue = typeof value === 'number' ? value.toFixed(4) : value;
  return (
    <div className="flex flex-col gap-1 p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors">
      <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider">{label}</span>
      <span className="text-lg font-semibold truncate" title={String(displayValue)}>{displayValue}</span>
    </div>
  );
};
