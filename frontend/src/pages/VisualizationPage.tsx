import React from 'react';
import { useParams } from 'react-router-dom';
import { useDatasetVisualizations } from '../hooks/useApi';
import { AlertCircle, LineChart, Maximize2 } from 'lucide-react';
import { motion } from 'framer-motion';

export const VisualizationPage: React.FC = () => {
  const { datasetId } = useParams<{ datasetId: string }>();
  const { data: viz, isLoading, error } = useDatasetVisualizations(datasetId!);
  
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
      <div className="flex h-full w-full flex-col gap-6 p-4 max-w-[1400px] mx-auto">
        <div className="h-10 w-64 bg-muted rounded-md animate-pulse"></div>
        <div className="h-[600px] w-full bg-card border border-border rounded-xl animate-pulse mt-4"></div>
      </div>
    );
  }

  if (error || !viz) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-destructive min-h-[500px]">
        <AlertCircle className="h-12 w-12 mb-4 opacity-80" />
        <h2 className="text-xl font-semibold">Failed to load visualizations</h2>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 pb-20 max-w-[1400px] mx-auto w-full pt-4">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
            <LineChart className="h-5 w-5 text-primary" />
          </div>
          Data Visualizations
        </h1>
        <p className="text-muted-foreground text-sm font-medium ml-14">Interactive charts and pre-rendered heatmaps.</p>
      </div>

      <div className="grid grid-cols-1 gap-8">
        {viz.charts?.map((chart: any, index: number) => (
          <motion.div
            key={chart.chart_id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="rounded-xl border border-border bg-card flex flex-col overflow-hidden shadow-sm group"
          >
            <div className="w-full flex justify-between items-center px-6 py-4 border-b border-border/50">
              <h3 className="text-lg font-semibold capitalize text-foreground flex items-center gap-2">
                {chart.type} Analysis
              </h3>
              {chart.html_url && (
                <a 
                  href={resolveUrl(chart.html_url)} 
                  target="_blank" 
                  rel="noreferrer"
                  className="flex items-center gap-2 text-xs font-medium text-muted-foreground hover:text-foreground bg-muted/50 hover:bg-muted px-3 py-1.5 rounded-full transition-colors border border-border/50"
                >
                  <Maximize2 className="h-3.5 w-3.5" /> Fullscreen Interactive
                </a>
              )}
            </div>
            
            <div className="p-6 bg-muted/10 flex justify-center items-center min-h-[400px]">
              {chart.png_url ? (
                <div className="w-full rounded-lg overflow-hidden border border-border/50 shadow-sm bg-background p-2">
                  <img src={resolveUrl(chart.png_url)} alt={`${chart.type} chart`} className="max-w-full h-auto w-full object-contain mix-blend-screen" />
                </div>
              ) : (
                <div className="w-full h-64 border border-dashed border-border rounded-xl flex flex-col items-center justify-center text-muted-foreground">
                  <AlertCircle className="h-8 w-8 mb-2 opacity-50" />
                  <span>{chart.error || "Image not available"}</span>
                </div>
              )}
            </div>
          </motion.div>
        ))}
        
        {(!viz.charts || viz.charts.length === 0) && (
          <div className="py-20 flex flex-col items-center justify-center text-center border border-border rounded-xl bg-card">
            <LineChart className="h-12 w-12 text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium text-foreground">No Charts Generated</h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-md">The visualization engine did not produce any charts for this dataset. This may occur if there are no suitable numeric columns to plot.</p>
          </div>
        )}
      </div>
    </div>
  );
};
