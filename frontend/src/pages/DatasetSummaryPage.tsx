import React from 'react';
import { useParams } from 'react-router-dom';
import { useDatasetSummary } from '../hooks/useApi';
import { Loader2, Database, AlertCircle, Type, Hash, Rows, Columns } from 'lucide-react';
import { motion } from 'framer-motion';

export const DatasetSummaryPage: React.FC = () => {
  const { datasetId } = useParams<{ datasetId: string }>();
  const { data: summary, isLoading, error } = useDatasetSummary(datasetId!);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-destructive">
        <AlertCircle className="h-16 w-16 mb-4" />
        <h2 className="text-2xl font-bold">Failed to load dataset summary</h2>
      </div>
    );
  }

  const memoryMB = (summary.memory_usage_bytes / (1024 * 1024)).toFixed(2);

  return (
    <div className="flex flex-col gap-8 pb-20">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Dataset Overview</h1>
        <p className="text-muted-foreground">ID: {datasetId}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard title="Total Rows" value={summary.total_rows.toLocaleString()} icon={Rows} delay={0.1} />
        <StatCard title="Total Columns" value={summary.total_columns} icon={Columns} delay={0.2} />
        <StatCard title="Numeric Columns" value={summary.numeric_columns.length} icon={Hash} delay={0.3} />
        <StatCard title="Categorical Columns" value={summary.categorical_columns.length} icon={Type} delay={0.4} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="glass-card p-6"
        >
          <div className="flex items-center gap-3 mb-6">
            <Database className="h-6 w-6 text-primary" />
            <h2 className="text-xl font-semibold">Memory & Structure</h2>
          </div>
          <div className="space-y-4">
            <div className="flex justify-between p-3 rounded-lg bg-white/5">
              <span className="text-muted-foreground">Memory Usage</span>
              <span className="font-medium">{memoryMB} MB</span>
            </div>
            <div className="flex justify-between p-3 rounded-lg bg-white/5">
              <span className="text-muted-foreground">Duplicate Rows</span>
              <span className="font-medium text-amber-400">{summary.duplicate_rows}</span>
            </div>
            <div className="flex justify-between p-3 rounded-lg bg-white/5">
              <span className="text-muted-foreground">Total Missing Cells</span>
              <span className="font-medium text-destructive">{summary.total_missing_cells}</span>
            </div>
          </div>
        </motion.div>

        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="glass-card p-6"
        >
          <div className="flex items-center gap-3 mb-6">
            <Type className="h-6 w-6 text-accent" />
            <h2 className="text-xl font-semibold">Data Types Breakdown</h2>
          </div>
          <div className="space-y-3 overflow-y-auto max-h-[200px] pr-2 custom-scrollbar">
            {Object.entries(summary.dtypes).map(([col, type]: [string, any]) => (
              <div key={col} className="flex justify-between p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors">
                <span className="font-medium truncate max-w-[60%]">{col}</span>
                <span className="text-accent text-sm font-mono bg-accent/10 px-2 py-1 rounded">{type}</span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
};

const StatCard = ({ title, value, icon: Icon, delay }: { title: string, value: string | number, icon: any, delay: number }) => (
  <motion.div 
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay }}
    className="glass-card p-6 flex items-center gap-4 group"
  >
    <div className="h-12 w-12 rounded-full bg-primary/20 flex items-center justify-center border border-primary/30 group-hover:scale-110 transition-transform">
      <Icon className="h-6 w-6 text-primary" />
    </div>
    <div>
      <p className="text-sm text-muted-foreground font-medium">{title}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  </motion.div>
);
