import React from 'react';
import { useParams } from 'react-router-dom';
import { FileText, Download, Share2, Loader2, AlertCircle, FileCheck2, ArrowRight } from 'lucide-react';
import { motion } from 'framer-motion';
import { useDatasetReport } from '../hooks/useApi';

export const ReportPage: React.FC = () => {
  const { datasetId } = useParams<{ datasetId: string }>();

  const { data: report, isLoading, error } = useDatasetReport(datasetId!);

  const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

  const resolveUrl = (url: string) => {
    if (!url) return '';
    if (url.startsWith('http')) return url;
    if (API_BASE_URL !== '/api/v1' && url.startsWith('/api/v1')) {
      return `${API_BASE_URL}${url.substring(7)}`;
    }
    return url;
  };

  if (isLoading) {
    return (
      <div className="flex flex-col h-full items-center justify-center gap-6 max-w-[1400px] mx-auto w-full min-h-[600px]">
        <div className="relative">
          <div className="absolute inset-0 rounded-full blur-xl bg-primary/20 animate-pulse"></div>
          <div className="relative h-20 w-20 rounded-2xl bg-card border border-primary/30 flex items-center justify-center shadow-[0_0_20px_rgba(var(--primary),0.3)]">
            <Loader2 className="h-8 w-8 text-primary animate-spin" />
          </div>
        </div>
        <div className="flex flex-col items-center">
          <h2 className="text-xl font-semibold text-foreground mb-2">Compiling Report</h2>
          <p className="text-sm text-muted-foreground animate-pulse">Assembling charts, statistics, and anomalies into PDF format...</p>
        </div>
        
        {/* Fake progress bar */}
        <div className="w-64 h-1.5 bg-muted rounded-full mt-4 overflow-hidden">
          <motion.div 
            initial={{ width: "0%" }}
            animate={{ width: "90%" }}
            transition={{ duration: 15, ease: "easeOut" }}
            className="h-full bg-primary"
          />
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="flex flex-col h-full items-center justify-center gap-4 text-destructive min-h-[500px]">
        <AlertCircle className="h-16 w-16 opacity-80" />
        <h2 className="text-2xl font-bold">Failed to generate report</h2>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 pb-20 h-full max-w-[1400px] mx-auto w-full pt-4">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
            <FileText className="h-5 w-5 text-primary" />
          </div>
          Executive Report
        </h1>
        <p className="text-muted-foreground text-sm font-medium ml-14">Downloadable business intelligence and dataset summary.</p>
      </div>

      <motion.div 
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="rounded-2xl border border-border bg-card p-12 flex flex-col items-center justify-center text-center flex-1 min-h-[500px] shadow-sm relative overflow-hidden group"
      >
        {/* Subtle background glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/5 rounded-full blur-[100px] pointer-events-none group-hover:bg-primary/10 transition-colors duration-1000"></div>
        
        <div className="h-24 w-24 rounded-2xl bg-muted flex items-center justify-center mb-8 border border-border shadow-sm relative z-10 group-hover:scale-110 group-hover:border-primary/30 group-hover:bg-primary/10 transition-all duration-500">
          <FileCheck2 className="h-10 w-10 text-foreground group-hover:text-primary transition-colors" />
        </div>
        
        <h2 className="text-3xl font-bold mb-4 text-foreground relative z-10">Report Successfully Generated</h2>
        <p className="text-muted-foreground max-w-lg mb-10 text-base leading-relaxed relative z-10">
          Your comprehensive analysis report is ready. It includes complete statistical profiles, outlier detection results, visualizations, and correlation insights formatted as a professional PDF.
        </p>
        
        <div className="flex flex-col sm:flex-row gap-4 relative z-10">
          <a 
            href={resolveUrl(report?.download_url || '')} 
            download
            className="group relative inline-flex items-center justify-center overflow-hidden rounded-lg bg-primary px-8 py-3.5 font-semibold text-primary-foreground shadow-sm hover:shadow-md transition-all hover:bg-primary/90"
          >
            <Download className="mr-2 h-4 w-4" />
            Download PDF
            <ArrowRight className="ml-2 h-4 w-4 opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all absolute right-4" />
          </a>
          
          <button className="inline-flex items-center justify-center rounded-lg border border-border bg-muted/50 px-6 py-3.5 font-medium text-foreground hover:bg-muted transition-all">
            <Share2 className="mr-2 h-4 w-4 text-muted-foreground" />
            Share Link
          </button>
        </div>
      </motion.div>
    </div>
  );
};
