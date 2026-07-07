import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useDatasetSummary } from '../hooks/useApi';
import { Loader2, AlertCircle, FileText, Activity, Layers, Hash, Sparkles, Database, Clock } from 'lucide-react';
import { motion } from 'framer-motion';

export const DatasetSummaryPage: React.FC = () => {
  const { datasetId } = useParams<{ datasetId: string }>();
  const { data: summary, isLoading, error } = useDatasetSummary(datasetId!);

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center min-h-[600px]">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground font-medium animate-pulse">Loading dataset metadata...</p>
        </div>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-destructive min-h-[600px]">
        <AlertCircle className="h-12 w-12 mb-4 opacity-80" />
        <h2 className="text-xl font-semibold">Failed to load dataset summary</h2>
      </div>
    );
  }

  const sizeStr = summary.file_size_mb > 1 
    ? `${summary.file_size_mb.toFixed(2)} MB` 
    : `${summary.file_size_kb.toFixed(2)} KB`;

  const uploadDate = new Date(summary.uploaded_at).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
  });

  return (
    <div className="flex flex-col lg:flex-row gap-8 pb-20 max-w-[1400px] mx-auto w-full pt-4">
      {/* Left Panel: Hero Insights (2/3) */}
      <div className="flex-1 flex flex-col gap-8">
        
        {/* Header Hero Area */}
        <motion.div 
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
          className="flex flex-col gap-2"
        >
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
              <Database className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-foreground">{summary.original_filename || 'Dataset Overview'}</h1>
              <p className="text-sm text-muted-foreground mt-1 flex items-center gap-2">
                <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500"></span>
                Ready for analysis
              </p>
            </div>
          </div>
        </motion.div>

        {/* Primary Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <MetricWidget 
            title="Total Records" 
            value={summary.rows.toLocaleString()} 
            icon={Layers} 
            delay={0.1}
            trend="+100% complete"
          />
          <MetricWidget 
            title="Total Features" 
            value={summary.columns} 
            icon={Hash} 
            delay={0.2}
            trend={`${summary.column_names?.length || 0} columns detected`}
          />
        </div>

        {/* Next Steps / Activity Feed */}
        <motion.div 
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.3 }}
          className="mt-4 flex flex-col gap-4"
        >
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              Recommended Workflows
            </h3>
          </div>
          
          <div className="grid grid-cols-1 gap-3">
            <WorkflowCard 
              to={`/dataset/${datasetId}/missing`}
              title="Assess Data Quality"
              description="Identify missing values and plan imputation strategies."
              icon={AlertCircle}
              delay={0.4}
            />
            <WorkflowCard 
              to={`/dataset/${datasetId}/stats`}
              title="Explore Statistics"
              description="View deep descriptive statistics and distributions for all features."
              icon={Activity}
              delay={0.5}
            />
            <WorkflowCard 
              to={`/dataset/${datasetId}/report`}
              title="Generate PDF Report"
              description="Export a comprehensive analysis report for stakeholders."
              icon={FileText}
              delay={0.6}
            />
          </div>
        </motion.div>
      </div>

      {/* Right Sidebar (1/3) */}
      <motion.div 
        initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5 }}
        className="w-full lg:w-80 shrink-0 flex flex-col gap-6"
      >
        {/* Sticky Details Panel */}
        <div className="sticky top-24 rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-foreground mb-4 uppercase tracking-wider">Dataset Metadata</h3>
          
          <div className="flex flex-col gap-4">
            <div className="flex justify-between items-center pb-3 border-b border-border/50">
              <span className="text-sm text-muted-foreground">ID</span>
              <span className="text-sm font-mono text-foreground truncate w-32 text-right" title={datasetId}>{datasetId ? datasetId.split('-')[0] : ''}...</span>
            </div>
            
            <div className="flex justify-between items-center pb-3 border-b border-border/50">
              <span className="text-sm text-muted-foreground">File Size</span>
              <span className="text-sm font-medium text-foreground">{sizeStr}</span>
            </div>
            
            <div className="flex justify-between items-center pb-3 border-b border-border/50">
              <span className="text-sm text-muted-foreground flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> Uploaded</span>
              <span className="text-xs font-medium text-foreground text-right">{uploadDate}</span>
            </div>
            
            <div className="pt-2">
              <span className="text-sm text-muted-foreground mb-3 block">Detected Schema</span>
              <div className="flex flex-wrap gap-2 max-h-[200px] overflow-y-auto custom-scrollbar pr-2">
                {summary.column_names?.map((col: string) => (
                  <span key={col} className="bg-muted text-foreground px-2 py-1 rounded text-xs font-medium border border-border/50">
                    {col}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

// --- Subcomponents ---

const MetricWidget = ({ title, value, icon: Icon, delay, trend }: { title: string, value: string | number, icon: any, delay: number, trend: string }) => (
  <motion.div 
    initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay, duration: 0.4 }}
    className="rounded-xl border border-border bg-card p-6 flex flex-col gap-4 hover:border-border/80 transition-colors"
  >
    <div className="flex items-center justify-between">
      <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
      <Icon className="h-4 w-4 text-muted-foreground/60" />
    </div>
    <div>
      <p className="text-3xl font-bold tracking-tight text-foreground">{value}</p>
      <p className="text-xs text-muted-foreground mt-1">{trend}</p>
    </div>
  </motion.div>
);

const WorkflowCard = ({ title, description, icon: Icon, to, delay }: { title: string, description: string, icon: any, to: string, delay: number }) => (
  <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay, duration: 0.4 }}>
    <Link 
      to={to} 
      className="group flex gap-4 p-4 rounded-xl border border-border bg-card hover:bg-muted/30 transition-all hover:border-primary/30"
    >
      <div className="h-10 w-10 shrink-0 rounded-lg bg-muted flex items-center justify-center group-hover:bg-primary/10 transition-colors">
        <Icon className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
      </div>
      <div className="flex flex-col justify-center">
        <h4 className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors">{title}</h4>
        <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{description}</p>
      </div>
    </Link>
  </motion.div>
);
