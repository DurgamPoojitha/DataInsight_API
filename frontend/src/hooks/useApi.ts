import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';

export const useDatasetSummary = (datasetId: string) => {
  return useQuery({
    queryKey: ['summary', datasetId],
    queryFn: async () => {
      const { data } = await api.get(`/dataset/${datasetId}/summary`);
      return data;
    },
    enabled: !!datasetId,
  });
};

export const useDatasetStatistics = (datasetId: string) => {
  return useQuery({
    queryKey: ['statistics', datasetId],
    queryFn: async () => {
      const { data } = await api.get(`/dataset/${datasetId}/statistics`);
      return data;
    },
    enabled: !!datasetId,
  });
};

export const useDatasetVisualizations = (datasetId: string) => {
  return useQuery({
    queryKey: ['visualizations', datasetId],
    queryFn: async () => {
      const { data } = await api.get(`/dataset/${datasetId}/visualizations`);
      return data;
    },
    enabled: !!datasetId,
  });
};

export const useDatasetMissing = (datasetId: string) => {
  return useQuery({
    queryKey: ['missing', datasetId],
    queryFn: async () => {
      const { data } = await api.get(`/dataset/${datasetId}/missing`);
      return data;
    },
    enabled: !!datasetId,
  });
};

export const useDatasetOutliers = (datasetId: string) => {
  return useQuery({
    queryKey: ['outliers', datasetId],
    queryFn: async () => {
      const { data } = await api.get(`/dataset/${datasetId}/outliers`);
      return data;
    },
    enabled: !!datasetId,
  });
};
