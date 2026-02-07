import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { holdingsAPI } from '../services/api';

export const useHoldings = (filters = {}) => {
  return useQuery({
    queryKey: ['holdings', filters],
    queryFn: () => holdingsAPI.getAll(filters).then(res => res.data),
  });
};

export const useAccountTypes = () => {
  return useQuery({
    queryKey: ['accountTypes'],
    queryFn: () => holdingsAPI.getAccountTypes().then(res => res.data),
    staleTime: Infinity, // Account types don't change
  });
};

export const useHolding = (id) => {
  return useQuery({
    queryKey: ['holding', id],
    queryFn: () => holdingsAPI.getOne(id).then(res => res.data),
    enabled: !!id,
  });
};

export const useCreateHolding = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) => holdingsAPI.create(data).then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['holdings'] });
    },
  });
};

export const useUpdateHolding = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => holdingsAPI.update(id, data).then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['holdings'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] }); // Refresh account breakdown
    },
  });
};

export const useDeleteHolding = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id) => holdingsAPI.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['holdings'] });
    },
  });
};
