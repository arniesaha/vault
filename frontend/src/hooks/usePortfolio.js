import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { analyticsAPI, pricesAPI, healthCheck, appStatus } from '../services/api';

// Health check hook to verify backend is ready
export const useHealthCheck = () => {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => healthCheck().then(res => res.data),
    retry: 10,
    retryDelay: (attemptIndex) => Math.min(1000 * (attemptIndex + 1), 5000),
    staleTime: 30 * 1000,
  });
};

// App status hook to track loading state
export const useAppStatus = (options = {}) => {
  return useQuery({
    queryKey: ['appStatus'],
    queryFn: () => appStatus().then(res => res.data),
    refetchInterval: (query) => {
      // Poll every second while loading, stop when ready
      const data = query.state.data;
      return data?.ready ? false : 1000;
    },
    retry: 3,
    retryDelay: 500,
    staleTime: 0, // Always fetch fresh status
    ...options,
  });
};

/**
 * Portfolio Summary with progressive loading:
 * 1. Instantly shows cached data (fast=true)
 * 2. Automatically refreshes with live data in background
 * @param {string} region - Filter by region: 'all', 'CA', or 'IN'
 */
export const usePortfolioSummary = (region = 'all') => {
  const queryClient = useQueryClient();
  
  // Main query - fetches live data
  const liveQuery = useQuery({
    queryKey: ['portfolio', 'summary', 'live', region],
    queryFn: () => analyticsAPI.getPortfolioSummary(false, region).then(res => res.data),
    refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(2000 * (attemptIndex + 1), 10000),
    // Don't show loading state if we have cached data
    placeholderData: () => queryClient.getQueryData(['portfolio', 'summary', 'cached', region]),
  });

  // Fast query - fetches cached data for instant display
  const cachedQuery = useQuery({
    queryKey: ['portfolio', 'summary', 'cached', region],
    queryFn: () => analyticsAPI.getPortfolioSummary(true, region).then(res => res.data),
    staleTime: Infinity, // Cache forever, we'll manually invalidate
    retry: 1,
  });

  // Return live data if available, otherwise cached
  const data = liveQuery.data || cachedQuery.data;
  const isLoading = !data && (liveQuery.isLoading || cachedQuery.isLoading);
  const isRefreshing = liveQuery.isFetching && !!cachedQuery.data;

  return {
    data,
    isLoading,
    isRefreshing,
    isError: liveQuery.isError && cachedQuery.isError,
    isFetching: liveQuery.isFetching,
    failureCount: liveQuery.failureCount,
    refetch: liveQuery.refetch,
    source: data?.source || 'unknown',
  };
};

/**
 * Allocation with progressive loading
 * @param {string} region - Filter by region: 'all', 'CA', or 'IN'
 */
export const useAllocation = (region = 'all') => {
  const queryClient = useQueryClient();
  
  const liveQuery = useQuery({
    queryKey: ['portfolio', 'allocation', 'live', region],
    queryFn: () => analyticsAPI.getAllocation(false, region).then(res => res.data),
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(2000 * (attemptIndex + 1), 10000),
    placeholderData: () => queryClient.getQueryData(['portfolio', 'allocation', 'cached', region]),
  });

  const cachedQuery = useQuery({
    queryKey: ['portfolio', 'allocation', 'cached', region],
    queryFn: () => analyticsAPI.getAllocation(true, region).then(res => res.data),
    staleTime: Infinity,
    retry: 1,
  });

  const data = liveQuery.data || cachedQuery.data;
  
  return {
    data,
    isLoading: !data && (liveQuery.isLoading || cachedQuery.isLoading),
    isRefreshing: liveQuery.isFetching && !!cachedQuery.data,
    source: data?.source || 'unknown',
  };
};

/**
 * Performance with progressive loading
 */
export const usePerformance = () => {
  const queryClient = useQueryClient();
  
  const liveQuery = useQuery({
    queryKey: ['portfolio', 'performance', 'live'],
    queryFn: () => analyticsAPI.getPerformance(false).then(res => res.data),
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(2000 * (attemptIndex + 1), 10000),
    placeholderData: () => queryClient.getQueryData(['portfolio', 'performance', 'cached']),
  });

  const cachedQuery = useQuery({
    queryKey: ['portfolio', 'performance', 'cached'],
    queryFn: () => analyticsAPI.getPerformance(true).then(res => res.data),
    staleTime: Infinity,
    retry: 1,
  });

  const data = liveQuery.data || cachedQuery.data;
  
  return {
    data,
    isLoading: !data && (liveQuery.isLoading || cachedQuery.isLoading),
    isRefreshing: liveQuery.isFetching && !!cachedQuery.data,
    source: data?.source || 'unknown',
  };
};

export const useRealizedGains = (region = 'all') => {
  return useQuery({
    queryKey: ['portfolio', 'realizedGains', region],
    queryFn: () => analyticsAPI.getRealizedGains(region).then(res => res.data),
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(2000 * (attemptIndex + 1), 10000),
  });
};

export const useAccountBreakdown = (fast = true) => {
  return useQuery({
    queryKey: ['portfolio', 'accountBreakdown', fast],
    queryFn: () => analyticsAPI.getAccountBreakdown(fast).then(res => res.data),
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(2000 * (attemptIndex + 1), 10000),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

export const useCurrentPrices = () => {
  return useQuery({
    queryKey: ['prices', 'current'],
    queryFn: () => pricesAPI.getCurrent().then(res => res.data),
    refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
    retry: 5,
    retryDelay: (attemptIndex) => Math.min(2000 * (attemptIndex + 1), 10000),
  });
};

export const useCachedPrices = () => {
  return useQuery({
    queryKey: ['prices', 'cached'],
    queryFn: () => pricesAPI.getCached().then(res => res.data),
    staleTime: Infinity,
    retry: 1,
  });
};

export const useRefreshPrices = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => pricesAPI.refresh().then(res => res.data),
    onSuccess: () => {
      // Invalidate all price and portfolio queries to trigger refresh
      queryClient.invalidateQueries({ queryKey: ['prices'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
    },
  });
};

// Exchange rates hook - cached for 1 hour
export const useExchangeRates = (base = 'CAD') => {
  return useQuery({
    queryKey: ['exchangeRates', base],
    queryFn: () => analyticsAPI.getExchangeRates(base).then(res => res.data),
    staleTime: 60 * 60 * 1000, // 1 hour
    gcTime: 24 * 60 * 60 * 1000, // 24 hours
    retry: 2,
  });
};
