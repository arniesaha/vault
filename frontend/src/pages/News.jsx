import { useState, useEffect } from 'react';
import Card, { EmptyState } from '../components/common/Card';
import api from '../services/api';

// Icons
const SparklesIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
  </svg>
);

const TrendingUpIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
  </svg>
);

const TrendingDownIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
  </svg>
);

const AlertTriangleIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
  </svg>
);

const PieChartIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
  </svg>
);

const GlobeIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const CheckCircleIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const RefreshIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
  </svg>
);

const LightBulbIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
  </svg>
);

const getIcon = (iconName, className) => {
  switch (iconName) {
    case 'trending-up':
      return <TrendingUpIcon className={className} />;
    case 'trending-down':
      return <TrendingDownIcon className={className} />;
    case 'alert-triangle':
      return <AlertTriangleIcon className={className} />;
    case 'pie-chart':
      return <PieChartIcon className={className} />;
    case 'globe':
      return <GlobeIcon className={className} />;
    default:
      return <SparklesIcon className={className} />;
  }
};

const severityColors = {
  high: {
    bg: 'bg-red-50 dark:bg-red-900/20',
    border: 'border-red-200 dark:border-red-800',
    icon: 'text-red-500 dark:text-red-400',
    badge: 'bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300'
  },
  medium: {
    bg: 'bg-amber-50 dark:bg-amber-900/20',
    border: 'border-amber-200 dark:border-amber-800',
    icon: 'text-amber-500 dark:text-amber-400',
    badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300'
  },
  low: {
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    border: 'border-blue-200 dark:border-blue-800',
    icon: 'text-blue-500 dark:text-blue-400',
    badge: 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300'
  }
};

const typeLabels = {
  take_profit: '🎯 Take Profit',
  review: '🔍 Review',
  rebalance: '⚖️ Rebalance',
  watch: '👀 Watch'
};

function HealthScore({ score, grade }) {
  const roundedScore = Math.round(score);
  
  const getGradeColor = () => {
    if (score >= 90) return 'text-green-500';
    if (score >= 80) return 'text-emerald-500';
    if (score >= 70) return 'text-yellow-500';
    if (score >= 60) return 'text-orange-500';
    return 'text-red-500';
  };

  const getGradeBg = () => {
    if (score >= 90) return 'from-green-500 to-emerald-500';
    if (score >= 80) return 'from-emerald-500 to-teal-500';
    if (score >= 70) return 'from-yellow-500 to-amber-500';
    if (score >= 60) return 'from-orange-500 to-red-400';
    return 'from-red-500 to-red-600';
  };

  return (
    <div className="flex items-center gap-6">
      <div className="relative">
        <div className={`w-24 h-24 rounded-full bg-gradient-to-br ${getGradeBg()} flex items-center justify-center shadow-lg`}>
          <div className="w-20 h-20 rounded-full bg-white dark:bg-secondary-900 flex items-center justify-center">
            <span className={`text-3xl font-bold ${getGradeColor()}`}>{grade}</span>
          </div>
        </div>
      </div>
      <div>
        <div className="text-sm text-secondary-500 dark:text-secondary-400 mb-1">Portfolio Health</div>
        <div className="text-2xl font-bold text-secondary-900 dark:text-secondary-100">{roundedScore}</div>
        <div className="text-sm text-secondary-500 dark:text-secondary-400 mt-1">
          {score >= 90 ? 'Excellent shape!' :
           score >= 80 ? 'Looking good' :
           score >= 70 ? 'Some attention needed' :
           score >= 60 ? 'Review recommended' :
           'Needs attention'}
        </div>
      </div>
    </div>
  );
}

function RecommendationCard({ recommendation }) {
  const colors = severityColors[recommendation.severity] || severityColors.low;
  
  return (
    <div className={`${colors.bg} ${colors.border} border rounded-xl p-4 hover:shadow-md transition-shadow`}>
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-lg bg-white dark:bg-secondary-800 ${colors.icon}`}>
          {getIcon(recommendation.icon, 'w-5 h-5')}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs px-2 py-0.5 rounded-full ${colors.badge}`}>
              {typeLabels[recommendation.type]}
            </span>
            {recommendation.symbol && (
              <span className="text-sm font-semibold text-secondary-900 dark:text-secondary-100">
                {recommendation.symbol}
              </span>
            )}
          </div>
          <h4 className="font-medium text-secondary-900 dark:text-secondary-100 mb-1">
            {recommendation.title}
          </h4>
          <p className="text-sm text-secondary-600 dark:text-secondary-400">
            {recommendation.description}
          </p>
          {recommendation.metric !== undefined && (
            <div className="mt-2 text-sm">
              <span className="text-secondary-500 dark:text-secondary-400">{recommendation.metric_label}: </span>
              <span className={`font-semibold ${
                recommendation.metric >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
              }`}>
                {recommendation.metric >= 0 ? '+' : ''}{recommendation.metric.toFixed(1)}%
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function InsightCard({ insight }) {
  return (
    <div className="bg-gradient-to-br from-primary-50 to-accent-50 dark:from-primary-900/20 dark:to-accent-900/20 border border-primary-100 dark:border-primary-800 rounded-xl p-4">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-white dark:bg-secondary-800 text-primary-500 dark:text-primary-400">
          <LightBulbIcon className="w-5 h-5" />
        </div>
        <div>
          <h4 className="font-medium text-secondary-900 dark:text-secondary-100 mb-1">{insight.title}</h4>
          <p className="text-sm text-secondary-600 dark:text-secondary-400">{insight.content}</p>
          {insight.generated_at && (
            <p className="text-xs text-secondary-400 dark:text-secondary-500 mt-2">
              Generated {new Date(insight.generated_at).toLocaleDateString()}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function SummaryBadges({ summary }) {
  const badges = [
    { key: 'take_profit', label: 'Take Profit', emoji: '🎯', color: 'bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300' },
    { key: 'review', label: 'Review', emoji: '🔍', color: 'bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300' },
    { key: 'rebalance', label: 'Rebalance', emoji: '⚖️', color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300' },
    { key: 'watch', label: 'Watch', emoji: '👀', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300' },
  ];

  return (
    <div className="flex flex-wrap gap-2">
      {badges.map(({ key, label, emoji, color }) => (
        summary[key] > 0 && (
          <span key={key} className={`px-3 py-1 rounded-full text-sm font-medium ${color}`}>
            {emoji} {summary[key]} {label}
          </span>
        )
      ))}
    </div>
  );
}

const recommendationTabs = [
  { key: 'all', label: 'All', emoji: '📋' },
  { key: 'take_profit', label: 'Take Profit', emoji: '🎯' },
  { key: 'review', label: 'Review', emoji: '🔍' },
  { key: 'rebalance', label: 'Rebalance', emoji: '⚖️' },
  { key: 'watch', label: 'Watch', emoji: '👀' },
];

export default function News() {
  const [recommendations, setRecommendations] = useState(null);
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('all');

  const fetchData = async (useLive = false) => {
    try {
      if (useLive) setRefreshing(true);
      else setLoading(true);
      
      const fastParam = useLive ? 'false' : 'true';
      const [recsResponse, insightsResponse] = await Promise.all([
        api.get(`/analytics/recommendations?fast=${fastParam}`),
        api.get('/analytics/insights').catch(() => ({ data: { insights: [] } }))
      ]);
      
      setRecommendations(recsResponse.data);
      setInsights(insightsResponse.data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch recommendations:', err);
      setError('Failed to load recommendations');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    // Load cached data first (instant), then auto-refresh with live
    fetchData(false).then(() => {
      fetchData(true);
    });
  }, []);

  const handleRefresh = () => {
    fetchData(true); // Always fetch live on manual refresh
  };

  if (loading) {
    return (
      <div className="container-app py-6 sm:py-8">
        <div className="mb-6 sm:mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold text-secondary-900 dark:text-secondary-100">News & Insights</h1>
          <p className="text-secondary-500 dark:text-secondary-400 mt-1">AI-powered analysis for your portfolio</p>
        </div>
        <Card className="animate-pulse">
          <div className="p-8 space-y-4">
            <div className="h-8 bg-secondary-200 dark:bg-secondary-700 rounded w-1/3"></div>
            <div className="h-4 bg-secondary-200 dark:bg-secondary-700 rounded w-2/3"></div>
            <div className="h-4 bg-secondary-200 dark:bg-secondary-700 rounded w-1/2"></div>
          </div>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container-app py-6 sm:py-8">
        <div className="mb-6 sm:mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold text-secondary-900 dark:text-secondary-100">News & Insights</h1>
        </div>
        <Card>
          <EmptyState
            icon={AlertTriangleIcon}
            title="Failed to load"
            description={error}
          />
        </Card>
      </div>
    );
  }

  const hasRecommendations = recommendations?.recommendations?.length > 0;
  const hasInsights = insights?.insights?.length > 0;

  return (
    <div className="container-app py-6 sm:py-8">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-6 sm:mb-8">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-secondary-900 dark:text-secondary-100">News & Insights</h1>
          <p className="text-secondary-500 dark:text-secondary-400 mt-1">AI-powered analysis for your portfolio</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="p-2 rounded-lg hover:bg-secondary-100 dark:hover:bg-secondary-800 transition-colors disabled:opacity-50 cursor-pointer"
          title="Refresh recommendations"
          aria-label="Refresh recommendations"
        >
          <RefreshIcon className={`w-5 h-5 text-secondary-600 dark:text-secondary-400 ${refreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Health Score & Summary */}
      <Card className="mb-6">
        <div className="p-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6">
            <HealthScore 
              score={recommendations?.health_score || 100} 
              grade={recommendations?.health_grade || 'A'} 
            />
            {recommendations?.summary && (
              <SummaryBadges summary={recommendations.summary} />
            )}
          </div>
        </div>
      </Card>

      {/* AI Insights */}
      {hasInsights && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-secondary-900 dark:text-secondary-100 mb-3 flex items-center gap-2">
            <SparklesIcon className="w-5 h-5 text-primary-500 dark:text-primary-400" />
            AI Insights
          </h2>
          <div className="space-y-3">
            {insights.insights.map((insight, index) => (
              <InsightCard key={index} insight={insight} />
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      <div>
        <h2 className="text-lg font-semibold text-secondary-900 dark:text-secondary-100 mb-3">
          Recommendations
        </h2>
        
        {hasRecommendations ? (
          <>
            {/* Tabs */}
            <div className="flex gap-2 mb-4 overflow-x-auto pb-2 scrollbar-hide">
              {recommendationTabs.map(({ key, label, emoji }) => {
                const count = key === 'all' 
                  ? recommendations.recommendations.length 
                  : recommendations.recommendations.filter(r => r.type === key).length;
                
                if (key !== 'all' && count === 0) return null;
                
                return (
                  <button
                    key={key}
                    onClick={() => setActiveTab(key)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
                      activeTab === key
                        ? 'bg-primary-500 text-white'
                        : 'bg-secondary-100 dark:bg-secondary-800 text-secondary-600 dark:text-secondary-400 hover:bg-secondary-200 dark:hover:bg-secondary-700'
                    }`}
                  >
                    <span>{emoji}</span>
                    <span>{label}</span>
                    <span className={`ml-1 px-1.5 py-0.5 rounded-full text-xs ${
                      activeTab === key
                        ? 'bg-white/20 text-white'
                        : 'bg-secondary-200 dark:bg-secondary-700 text-secondary-500 dark:text-secondary-400'
                    }`}>
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Filtered Recommendations */}
            <div className="grid gap-3">
              {recommendations.recommendations
                .filter(rec => activeTab === 'all' || rec.type === activeTab)
                .map((rec, index) => (
                  <RecommendationCard key={index} recommendation={rec} />
                ))}
            </div>
          </>
        ) : (
          <Card>
            <div className="p-8 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 dark:bg-green-900/30 rounded-full mb-4">
                <CheckCircleIcon className="w-8 h-8 text-green-500 dark:text-green-400" />
              </div>
              <h3 className="text-lg font-semibold text-secondary-900 dark:text-secondary-100 mb-2">
                All Good! 🎉
              </h3>
              <p className="text-secondary-500 dark:text-secondary-400 max-w-md mx-auto">
                Your portfolio looks well-balanced. No immediate actions recommended.
                Keep monitoring and stay the course.
              </p>
            </div>
          </Card>
        )}
      </div>

      {/* Last Updated */}
      {recommendations?.generated_at && (
        <p className="text-xs text-secondary-400 dark:text-secondary-500 mt-4 text-center">
          Last updated: {new Date(recommendations.generated_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}
