import React from 'react';
import { useParams } from 'react-router-dom';
import { FileText, Download, Share2, Loader2, AlertCircle } from 'lucide-react';
import { motion } from 'framer-motion';
import { useDatasetReport } from '../hooks/useApi';

export const ReportPage: React.FC = () => {
  const { datasetId } = useParams<{ datasetId: string }>();

  const { data: report, isLoading, error } = useDatasetReport(datasetId!);

  // Get API base URL for image and link resolution
  const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

  // Helper to resolve URLs
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
      <div className="flex flex-col h-full items-center justify-center gap-4">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
        <h2 className="text-xl font-medium text-muted-foreground animate-pulse">Generating comprehensive PDF report...</h2>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="flex flex-col h-full items-center justify-center gap-4 text-destructive">
        <AlertCircle className="h-16 w-16" />
        <h2 className="text-2xl font-bold">Failed to generate report</h2>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 pb-20 h-full">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Executive Report</h1>
        <p className="text-muted-foreground">Download the complete AI-generated business intelligence report.</p>
      </div>

      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="glass-card p-10 flex flex-col items-center justify-center text-center flex-1 min-h-[400px]"
      >
        <div className="h-24 w-24 rounded-full bg-primary/20 flex items-center justify-center mb-8 border border-primary/30">
          <FileText className="h-12 w-12 text-primary" />
        </div>
        
        <h2 className="text-3xl font-bold mb-4">Report Ready</h2>
        <p className="text-muted-foreground max-w-lg mb-8 text-lg">
          Your comprehensive dataset analysis report has been generated. It includes all statistical profiles, outlier detection results, and correlation insights formatted as a professional PDF.
        </p>
        
        <div className="flex gap-4">
          <a 
            href={resolveUrl(report?.download_url || '')} 
            download
            className="inline-flex items-center justify-center overflow-hidden rounded-xl bg-gradient-to-tr from-primary to-accent px-8 py-4 font-semibold text-white shadow-[0_0_30px_rgba(124,58,237,0.3)] transition-all hover:shadow-[0_0_50px_rgba(124,58,237,0.5)] hover:scale-105"
          >
            <Download className="mr-2 h-5 w-5" />
            Download PDF Report
          </a>
          
          <button className="inline-flex items-center justify-center rounded-xl border border-white/10 glass px-6 py-4 font-semibold text-foreground transition-all hover:bg-white/10 hover:scale-105">
            <Share2 className="mr-2 h-5 w-5" />
            Share
          </button>
        </div>
      </motion.div>
    </div>
  );
};
