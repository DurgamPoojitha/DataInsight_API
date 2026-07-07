import React from 'react';
import { useParams } from 'react-router-dom';
import { useDatasetSummary } from '../hooks/useApi';
import { Loader2, Database, AlertCircle, Type, Rows, Columns } from 'lucide-react';
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

  const sizeStr = summary.file_size_mb > 1 
    ? `${summary.file_size_mb.toFixed(2)} MB` 
    : `${summary.file_size_kb.toFixed(2)} KB`;

  return (
    <div className="flex flex-col gap-8 pb-20">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Dataset Overview</h1>
        <p className="text-muted-foreground">ID: {datasetId}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard title="Total Rows" value={summary.rows.toLocaleString()} icon={Rows} delay={0.1} />
        <StatCard title="Total Columns" value={summary.columns} icon={Columns} delay={0.2} />
        <StatCard title="File Size" value={sizeStr} icon={Database} delay={0.3} />
        <StatCard title="Uploaded At" value={new Date(summary.uploaded_at).toLocaleDateString()} icon={Type} delay={0.4} />
      </div>

      <div className="grid grid-cols-1 gap-6">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="glass-card p-6"
        >
          <div className="flex items-center gap-3 mb-6">
            <Type className="h-6 w-6 text-accent" />
            <h2 className="text-xl font-semibold">Columns ({summary.column_names?.length || 0})</h2>
          </div>
          <div className="flex flex-wrap gap-2 overflow-y-auto max-h-[300px] pr-2 custom-scrollbar">
            {summary.column_names?.map((col: string) => (
              <span key={col} className="bg-white/5 border border-white/10 px-3 py-1.5 rounded-md text-sm">
                {col}
              </span>
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
