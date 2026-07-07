import React from 'react';
import { useParams } from 'react-router-dom';
import { useDatasetVisualizations } from '../hooks/useApi';
import { Loader2, AlertCircle, ExternalLink } from 'lucide-react';
import { motion } from 'framer-motion';

export const VisualizationPage: React.FC = () => {
  const { datasetId } = useParams<{ datasetId: string }>();
  const { data: viz, isLoading, error } = useDatasetVisualizations(datasetId!);
  
  // Get API base URL for image and link resolution
  const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

  // Helper to resolve URLs
  const resolveUrl = (url: string) => {
    if (!url) return '';
    if (url.startsWith('http')) return url;
    // The backend returns URLs starting with /api/v1, so we remove the duplicate if VITE_API_URL is set
    if (API_BASE_URL !== '/api/v1' && url.startsWith('/api/v1')) {
      return `${API_BASE_URL}${url.substring(7)}`;
    }
    // If VITE_API_URL is not set, we can just use the relative URL returned by the backend
    return url;
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !viz) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-destructive">
        <AlertCircle className="h-16 w-16 mb-4" />
        <h2 className="text-2xl font-bold">Failed to load visualizations</h2>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 pb-20">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Generated Visualizations</h1>
        <p className="text-muted-foreground">Pre-generated charts exported from the backend engine.</p>
      </div>

      <div className="grid grid-cols-1 gap-8">
        {viz.charts?.map((chart: any) => (
          <motion.div
            key={chart.chart_id}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="glass-card p-4 flex flex-col items-center"
          >
            <div className="w-full flex justify-between items-center mb-4 px-2">
              <h3 className="text-xl font-semibold capitalize">{chart.type} Chart</h3>
              {chart.html_url && (
                <a 
                  href={resolveUrl(chart.html_url)} 
                  target="_blank" 
                  rel="noreferrer"
                  className="flex items-center gap-2 text-sm text-primary hover:text-accent transition-colors"
                >
                  <ExternalLink className="h-4 w-4" /> Interactive HTML
                </a>
              )}
            </div>
            
            {chart.png_url ? (
              <div className="w-full bg-white/5 rounded-xl overflow-hidden p-4 flex justify-center">
                <img src={resolveUrl(chart.png_url)} alt={`${chart.type} chart`} className="max-w-full h-auto rounded-lg shadow-2xl" />
              </div>
            ) : (
              <div className="w-full h-64 bg-white/5 rounded-xl flex items-center justify-center text-muted-foreground">
                {chart.error || "Image not available"}
              </div>
            )}
          </motion.div>
        ))}
        
        {(!viz.charts || viz.charts.length === 0) && (
          <div className="p-8 text-center text-muted-foreground glass-card">
            No charts were generated.
          </div>
        )}
      </div>
    </div>
  );
};
