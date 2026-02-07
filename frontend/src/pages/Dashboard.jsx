import { useState } from 'react';
import { EmptyState } from '../components/common/Card';
import LoadingSpinner, { SkeletonCard, SkeletonChart } from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';
import SummaryCards from '../components/dashboard/SummaryCards';
import AllocationCharts from '../components/dashboard/AllocationCharts';
import AccountBreakdownChart from '../components/dashboard/AccountBreakdownChart';
import TopHoldings from '../components/dashboard/TopHoldings';
import PortfolioValueChart from '../components/dashboard/PortfolioValueChart';
import RegionFilter from '../components/dashboard/RegionFilter';
import CurrencyToggle from '../components/dashboard/CurrencyToggle';
import { usePortfolioSummary, useAllocation, usePerformance, useRefreshPrices, useAppStatus, useRealizedGains, useExchangeRates } from '../hooks/usePortfolio';
import { Link } from 'react-router-dom';
import Button from '../components/common/Button';

// Icons
const PlusIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
  </svg>
);

const ChartIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
  </svg>
);

const RefreshIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
  </svg>
);

// Subtle refresh indicator shown when updating prices in background
function RefreshIndicator({ source }) {
  return (
    <div className="inline-flex items-center gap-2 px-3 py-1 bg-blue-50 text-blue-600 text-sm rounded-full">
      <RefreshIcon className="w-4 h-4 animate-spin" />
      <span>Updating prices...</span>
    </div>
  );
}

// Data source badge
function SourceBadge({ source, isRefreshing }) {
  if (isRefreshing) {
    return <RefreshIndicator />;
  }
  
  if (source === 'cache') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-yellow-50 text-yellow-700 text-xs rounded">
        📦 Cached prices
      </span>
    );
  }
  
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-50 text-green-700 text-xs rounded">
      ✓ Live prices
    </span>
  );
}

function InitializingState() {
  return (
    <div className="container-app py-8">
      <div className="mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold text-secondary-900">Dashboard</h1>
        <p className="text-secondary-500 mt-1">Overview of your investment portfolio</p>
      </div>

      {/* Show skeleton UI immediately instead of blocking spinner */}
      <div className="space-y-6 sm:space-y-8">
        {/* Skeleton Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          {[1, 2, 3, 4].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
        
        {/* Skeleton Chart */}
        <div className="bg-white rounded-xl shadow-soft border border-secondary-100 p-6">
          <div className="h-4 w-32 bg-secondary-200 rounded animate-pulse mb-4" />
          <div className="h-64 bg-secondary-100 rounded animate-pulse" />
        </div>
        
        {/* Loading message */}
        <div className="text-center py-4">
          <div className="inline-flex items-center gap-2 text-secondary-500">
            <RefreshIcon className="w-4 h-4 animate-spin" />
            <span>Loading portfolio data...</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [region, setRegion] = useState('all');
  const [displayCurrency, setDisplayCurrency] = useState('CAD');
  
  const {
    data: summary,
    isLoading: summaryLoading,
    isRefreshing: summaryRefreshing,
    isError: summaryError,
    isFetching: summaryFetching,
    failureCount,
    refetch,
    source: summarySource,
  } = usePortfolioSummary(region);
  
  const { 
    data: allocation, 
    isLoading: allocationLoading,
    isRefreshing: allocationRefreshing,
  } = useAllocation(region);
  
  const { 
    data: performance, 
    isLoading: performanceLoading 
  } = usePerformance();
  
  const { data: realizedGains, isLoading: realizedGainsLoading } = useRealizedGains(region);
  const refreshPrices = useRefreshPrices();
  const { data: appStatus } = useAppStatus();
  const { data: exchangeRatesData } = useExchangeRates('CAD');
  
  // Extract rates from API response
  const exchangeRates = exchangeRatesData?.rates;

  // Check if any data is refreshing in background
  const isRefreshing = summaryRefreshing || allocationRefreshing;

  // Show skeleton only if we have NO data at all (not even cached)
  if (summaryLoading && !summary) {
    return <InitializingState />;
  }

  // Only show error after all retries have failed AND we have no data
  if (summaryError && !summary) {
    return (
      <div className="container-app py-8">
        <div className="mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold text-secondary-900">Dashboard</h1>
          <p className="text-secondary-500 mt-1">Overview of your investment portfolio</p>
        </div>
        <div className="bg-white rounded-xl shadow-soft border border-secondary-100 p-8">
          <ErrorMessage
            message="Unable to load portfolio data. Please check if the backend server is running."
          />
          <div className="mt-4 flex justify-center">
            <Button onClick={() => refetch()} icon={RefreshIcon}>
              Try Again
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const hasHoldings = summary && summary.holdings_count > 0;

  return (
    <div className="container-app py-6 sm:py-8">
      {/* Page Header */}
      <div className="mb-6 sm:mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-secondary-900">Dashboard</h1>
          <p className="text-secondary-500 mt-1">Overview of your investment portfolio</p>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Region Filter */}
          <RegionFilter value={region} onChange={setRegion} />
          
          {/* Currency Toggle */}
          <CurrencyToggle value={displayCurrency} onChange={setDisplayCurrency} rates={exchangeRates} />
          
          {/* Price source indicator */}
          {hasHoldings && (
            <SourceBadge source={summarySource} isRefreshing={isRefreshing} />
          )}
        </div>
      </div>

      {!hasHoldings ? (
        <div className="bg-white rounded-xl shadow-soft border border-secondary-100">
          <EmptyState
            icon={ChartIcon}
            title="Welcome to Portfolio Tracker"
            description="Start tracking your investments by adding your first holding. We support stocks from Canadian, US, and Indian markets."
            action={
              <Link to="/holdings">
                <Button icon={PlusIcon}>Add Your First Holding</Button>
              </Link>
            }
          />
        </div>
      ) : (
        <div className="space-y-6 sm:space-y-8">
          {/* Summary Cards */}
          <section>
            <SummaryCards 
              summary={summary} 
              realizedGains={realizedGains} 
              isLoading={summaryLoading || realizedGainsLoading}
              displayCurrency={displayCurrency}
              exchangeRates={exchangeRates}
            />
          </section>

          {/* Portfolio Value Chart */}
          <section>
            <PortfolioValueChart />
          </section>

          {/* Allocation Charts */}
          <section>
            <AllocationCharts allocation={allocation} isLoading={allocationLoading && !allocation} />
          </section>

          {/* Account Breakdown Chart */}
          <section>
            <AccountBreakdownChart />
          </section>

          {/* Top Holdings Table */}
          <section>
            <TopHoldings holdings={allocation?.top_holdings} isLoading={allocationLoading && !allocation} />
          </section>
        </div>
      )}
    </div>
  );
}
