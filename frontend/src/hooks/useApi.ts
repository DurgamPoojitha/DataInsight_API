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
        columns: null,
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
      const { data } = await api.get(`/missing-values/report/${datasetId}`);
      return data.data;
    },
    enabled: !!datasetId,
  });
};

export const useDatasetOutliers = (datasetId: string) => {
  return useQuery({
    queryKey: ['outliers', datasetId],
    queryFn: async () => {
      const { data } = await api.get(`/outliers/detect/${datasetId}`);
      return data.data;
    },
    enabled: !!datasetId,
  });
};

// Visualization query needs to hit the batch endpoint with a default payload.
// For a robust system, we would first get numeric columns and generate a payload, 
// but for now we'll just request a correlation heatmap.
export const useDatasetVisualizations = (datasetId: string) => {
  return useQuery({
    queryKey: ['visualizations', datasetId],
    queryFn: async () => {
      const { data } = await api.post(`/visualizations/generate/${datasetId}`, {
        charts: [
          { type: 'heatmap', columns: [] }
        ],
        export_format: 'both'
      });
      return data.data;
    },
    enabled: !!datasetId,
  });
};
