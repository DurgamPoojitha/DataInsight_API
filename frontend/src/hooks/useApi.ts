import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';

export const useDatasetSummary = (datasetId: string) => {
  return useQuery({
    queryKey: ['summary', datasetId],
    queryFn: async () => {
      const { data } = await api.get(`/datasets/${datasetId}`);
      return data.data;
    },
    enabled: !!datasetId,
  });
};

export const useDatasetStatistics = (datasetId: string) => {
  return useQuery({
    queryKey: ['statistics', datasetId],
    queryFn: async () => {
      const { data } = await api.post(`/analysis/describe/${datasetId}`, {
        columns: [],
        nan_policy: 'omit'
      });
      return data.data;
    },
    enabled: !!datasetId,
  });
};

export const useDatasetMissing = (datasetId: string) => {
  return useQuery({
    queryKey: ['missing', datasetId],
    queryFn: async () => {
      const { data } = await api.post(`/missing-values/analyse/${datasetId}`);
      return data.data;
    },
    enabled: !!datasetId,
  });
};

export const useDatasetOutliers = (datasetId: string) => {
  return useQuery({
    queryKey: ['outliers', datasetId],
    queryFn: async () => {
      const { data } = await api.post(`/outliers/detect/${datasetId}`, {
        method: 'iqr',
        columns: [],
        generate_boxplots: true
      });
      return data.data;
    },
    enabled: !!datasetId,
  });
};

export const useDatasetVisualizations = (datasetId: string) => {
  return useQuery({
    queryKey: ['visualizations', datasetId],
    queryFn: async () => {
      const { data } = await api.post(`/visualizations/generate/${datasetId}`, {
        charts: [
          { type: 'heatmap', columns: [] }
        ],
        export_format: 'both' // We now have Chromium in Docker, so PNGs will work
      });
      return data.data;
    },
    enabled: !!datasetId,
  });
};

export const useDatasetReport = (datasetId: string) => {
  return useQuery({
    queryKey: ['report', datasetId],
    queryFn: async () => {
      const { data } = await api.post(`/reports/generate/${datasetId}`, {
        include_visualizations: true // We can embed charts in PDF again
      });
      return data.data;
    },
    enabled: !!datasetId,
  });
};
