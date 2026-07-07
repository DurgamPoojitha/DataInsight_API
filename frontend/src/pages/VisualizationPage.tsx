import React from 'react';
import { useParams } from 'react-router-dom';
import { useDatasetVisualizations } from '../hooks/useApi';
import { Loader2, AlertCircle, Maximize2 } from 'lucide-react';
import { motion } from 'framer-motion';
import Plot from 'react-plotly.js';

export const VisualizationPage: React.FC = () => {
  const { datasetId } = useParams<{ datasetId: string }>();
  const { data: viz, isLoading, error } = useDatasetVisualizations(datasetId!);

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

  // The backend returns a dictionary where keys are plot names (e.g., 'histogram_Age')
  // and values are the Plotly JSON figure strings.
  const plots = Object.entries(viz.plots).map(([key, figStr]: [string, any]) => {
    let figure = null;
    try {
      figure = JSON.parse(figStr);
    } catch (e) {
      console.error('Failed to parse plot JSON for', key);
    }
    return { key, figure };
  }).filter(p => p.figure);

  return (
    <div className="flex flex-col gap-8 pb-20">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Interactive Visualizations</h1>
        <p className="text-muted-foreground">AI-generated plots for numeric columns.</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        {plots.map((plot, i) => (
          <motion.div
            key={plot.key}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.1 }}
            className="glass-card p-2 flex flex-col h-[450px] relative group"
          >
            <div className="absolute top-4 right-4 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
              <button className="p-2 bg-background/80 backdrop-blur rounded-md border border-white/10 hover:bg-white/10">
                <Maximize2 className="h-4 w-4 text-foreground" />
              </button>
            </div>
            <div className="flex-1 w-full h-full rounded-xl overflow-hidden bg-white/5">
              <Plot
                data={plot.figure.data}
                layout={{
                  ...plot.figure.layout,
                  autosize: true,
                  paper_bgcolor: 'transparent',
                  plot_bgcolor: 'transparent',
                  font: { color: '#e5e5e5' },
                  margin: { t: 40, r: 20, l: 40, b: 40 },
                }}
                config={{ responsive: true, displayModeBar: true, displaylogo: false }}
                style={{ width: '100%', height: '100%' }}
                useResizeHandler={true}
              />
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};
