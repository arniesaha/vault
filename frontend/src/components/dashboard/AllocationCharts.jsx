import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { SkeletonChart } from '../common/LoadingSpinner';

// Updated color palette matching the design system
const COLORS = {
  // Country colors
  US: '#3b82f6',    // blue
  CA: '#dc2626',    // red
  IN: '#f97316',    // orange

  // Exchange colors
  NASDAQ: '#3b82f6', // blue
  NYSE: '#60a5fa',   // light blue
  TSX: '#dc2626',    // red
  'TSX-V': '#f87171', // light red
  NSE: '#f97316',    // orange
  BSE: '#fb923c',    // light orange
};

const COUNTRY_NAMES = {
  US: 'United States',
  CA: 'Canada',
  IN: 'India',
};

const RADIAN = Math.PI / 180;

const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  if (percent < 0.05) return null;

  return (
    <text
      x={x}
      y={y}
      fill="white"
      textAnchor="middle"
      dominantBaseline="central"
      className="text-xs font-bold"
      style={{ textShadow: '0 1px 2px rgba(0,0,0,0.3)' }}
    >
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white px-4 py-3 border border-secondary-200 rounded-lg shadow-lg">
        <p className="font-semibold text-secondary-900">{payload[0].name}</p>
        <p className="text-sm text-secondary-600 mt-1">
          <span className="font-medium">{payload[0].value.toFixed(1)}%</span> of portfolio
        </p>
      </div>
    );
  }
  return null;
};

const CustomLegend = ({ payload }) => {
  return (
    <div className="flex flex-wrap justify-center gap-x-4 gap-y-2 mt-4">
      {payload.map((entry, index) => (
        <div key={index} className="flex items-center gap-2">
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-sm text-secondary-600">
            {entry.value}
            <span className="font-medium text-secondary-900 ml-1">
              ({entry.payload.value.toFixed(1)}%)
            </span>
          </span>
        </div>
      ))}
    </div>
  );
};

function ChartCard({ title, subtitle, children, isEmpty }) {
  return (
    <div className="bg-white rounded-xl shadow-soft border border-secondary-100 p-6">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-secondary-900">{title}</h3>
        {subtitle && <p className="text-sm text-secondary-500 mt-0.5">{subtitle}</p>}
      </div>
      {isEmpty ? (
        <div className="flex items-center justify-center h-[300px] text-secondary-400">
          <div className="text-center">
            <svg className="w-12 h-12 mx-auto mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
            </svg>
            <p className="text-sm">No data available</p>
          </div>
        </div>
      ) : (
        children
      )}
    </div>
  );
}

export default function AllocationCharts({ allocation, isLoading }) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SkeletonChart />
        <SkeletonChart />
      </div>
    );
  }

  if (!allocation) {
    return null;
  }

  // Prepare country data with full names
  const countryData = Object.entries(allocation.by_country || {})
    .map(([code, value]) => ({
      name: COUNTRY_NAMES[code] || code,
      code,
      value: parseFloat(value.toFixed(2)),
    }))
    .sort((a, b) => b.value - a.value);

  // Prepare exchange data
  const exchangeData = Object.entries(allocation.by_exchange || {})
    .map(([name, value]) => ({
      name,
      value: parseFloat(value.toFixed(2)),
    }))
    .sort((a, b) => b.value - a.value);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Country Allocation */}
      <ChartCard
        title="Geographic Allocation"
        subtitle="Distribution by country"
        isEmpty={countryData.length === 0}
      >
        <ResponsiveContainer width="100%" height={320}>
          <PieChart margin={{ top: 10, right: 0, bottom: 0, left: 0 }}>
            <Pie
              data={countryData}
              cx="50%"
              cy="40%"
              labelLine={false}
              label={renderCustomizedLabel}
              outerRadius={90}
              innerRadius={35}
              fill="#8884d8"
              dataKey="value"
              paddingAngle={2}
            >
              {countryData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={COLORS[entry.code] || `hsl(${index * 137.5}, 70%, 50%)`}
                  stroke="white"
                  strokeWidth={2}
                />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend content={<CustomLegend />} />
          </PieChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* Exchange Allocation */}
      <ChartCard
        title="Exchange Allocation"
        subtitle="Distribution by stock exchange"
        isEmpty={exchangeData.length === 0}
      >
        <ResponsiveContainer width="100%" height={320}>
          <PieChart margin={{ top: 10, right: 0, bottom: 0, left: 0 }}>
            <Pie
              data={exchangeData}
              cx="50%"
              cy="40%"
              labelLine={false}
              label={renderCustomizedLabel}
              outerRadius={90}
              innerRadius={35}
              fill="#8884d8"
              dataKey="value"
              paddingAngle={2}
            >
              {exchangeData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={COLORS[entry.name] || `hsl(${index * 60}, 65%, 50%)`}
                  stroke="white"
                  strokeWidth={2}
                />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend content={<CustomLegend />} />
          </PieChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}
