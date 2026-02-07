import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import { SkeletonChart } from '../common/LoadingSpinner';
import { useAccountBreakdown } from '../../hooks/usePortfolio';
import { formatCurrency, formatPercent } from '../../utils/formatters';

// Colors for account types
const ACCOUNT_COLORS = {
  TFSA: '#10b981',    // green (tax-free)
  RRSP: '#3b82f6',    // blue (retirement)
  FHSA: '#8b5cf6',    // purple (home savings)
  RESP: '#f59e0b',    // amber (education)
  LIRA: '#6366f1',    // indigo (locked-in)
  RRIF: '#0ea5e9',    // sky (retirement income)
  NON_REG: '#ef4444', // red (taxable)
  MARGIN: '#f97316',  // orange (margin)
  DEMAT: '#14b8a6',   // teal (Indian stocks)
  MF_INDIA: '#a855f7', // violet (Indian mutual funds)
  FD_INDIA: '#7c3aed', // purple-600 (Indian fixed deposits)
  PPF_INDIA: '#22c55e', // green-500 (Indian PPF - tax-free)
  NRO: '#ec4899',     // pink (NRO)
  NRE: '#f43f5e',     // rose (NRE)
  UNASSIGNED: '#9ca3af', // gray (not set)
};

const ACCOUNT_NAMES = {
  TFSA: 'TFSA',
  RRSP: 'RRSP',
  FHSA: 'FHSA',
  RESP: 'RESP',
  LIRA: 'LIRA',
  RRIF: 'RRIF',
  NON_REG: 'Non-Registered',
  MARGIN: 'Margin',
  DEMAT: 'DEMAT',
  MF_INDIA: 'MF India',
  FD_INDIA: 'FD India',
  PPF_INDIA: 'PPF India',
  NRO: 'NRO',
  NRE: 'NRE',
  UNASSIGNED: 'Unassigned',
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
    const data = payload[0].payload;
    return (
      <div className="bg-white px-4 py-3 border border-secondary-200 rounded-lg shadow-lg">
        <p className="font-semibold text-secondary-900">{data.name}</p>
        <p className="text-sm text-secondary-600 mt-1">
          <span className="font-medium">{formatCurrency(data.value_cad, 'CAD')}</span>
        </p>
        <p className="text-sm text-secondary-500">
          {data.allocation_pct.toFixed(1)}% of portfolio
        </p>
        {data.gain_pct !== undefined && (
          <p className={`text-sm mt-1 ${data.gain_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {data.gain_pct >= 0 ? '+' : ''}{data.gain_pct.toFixed(1)}% return
          </p>
        )}
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
              ({entry.payload.allocation_pct.toFixed(1)}%)
            </span>
          </span>
        </div>
      ))}
    </div>
  );
};

// Tax advantage indicator
function TaxBadge({ isTaxAdvantaged }) {
  if (isTaxAdvantaged) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
        Tax-Free
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
      Taxable
    </span>
  );
}

export default function AccountBreakdownChart() {
  const { data, isLoading, isError } = useAccountBreakdown(true);

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl shadow-soft border border-secondary-100 p-6">
        <div className="h-4 w-48 bg-secondary-200 rounded animate-pulse mb-4" />
        <SkeletonChart />
      </div>
    );
  }

  if (isError || !data) {
    return null;
  }

  const { by_account_type, tax_advantaged_total, taxable_total, tax_advantaged_pct, total_value_cad } = data;

  // Prepare chart data
  const chartData = Object.entries(by_account_type || {})
    .map(([code, info]) => ({
      code,
      name: ACCOUNT_NAMES[code] || code,
      value_cad: info.value_cad,
      allocation_pct: info.allocation_pct,
      gain_pct: info.gain_pct,
      is_tax_advantaged: info.is_tax_advantaged,
      holdings_count: info.holdings_count,
    }))
    .filter(item => item.value_cad > 0)
    .sort((a, b) => b.value_cad - a.value_cad);

  if (chartData.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-soft border border-secondary-100 p-6">
        <h3 className="text-lg font-semibold text-secondary-900 mb-2">Account Breakdown</h3>
        <p className="text-sm text-secondary-500 mb-4">Distribution by account type</p>
        <div className="flex items-center justify-center h-[200px] text-secondary-400">
          <div className="text-center">
            <p className="text-sm">No account types assigned yet.</p>
            <p className="text-xs mt-1">Assign account types to your holdings to see the breakdown.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-soft border border-secondary-100 p-6">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-secondary-900">Account Breakdown</h3>
        <p className="text-sm text-secondary-500 mt-0.5">Distribution by account type (TFSA, RRSP, etc.)</p>
      </div>

      {/* Tax Summary Bar */}
      <div className="mb-6 p-4 bg-secondary-50 rounded-lg">
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-1 mb-2">
          <span className="text-sm font-medium text-secondary-700">Tax-Advantaged vs Taxable</span>
          <span className="text-sm text-secondary-500">
            {formatPercent(tax_advantaged_pct)} tax-advantaged
          </span>
        </div>
        <div className="h-4 bg-secondary-200 rounded-full overflow-hidden flex">
          <div
            className="h-full bg-green-500 transition-all duration-500"
            style={{ width: `${tax_advantaged_pct}%` }}
            title={`Tax-Advantaged: ${formatCurrency(tax_advantaged_total, 'CAD')}`}
          />
          <div
            className="h-full bg-red-400 transition-all duration-500"
            style={{ width: `${100 - tax_advantaged_pct}%` }}
            title={`Taxable: ${formatCurrency(taxable_total, 'CAD')}`}
          />
        </div>
        <div className="flex justify-between mt-2 text-xs text-secondary-500">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500"></span>
            Tax-Free: {formatCurrency(tax_advantaged_total, 'CAD')}
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-400"></span>
            Taxable: {formatCurrency(taxable_total, 'CAD')}
          </span>
        </div>
      </div>

      {/* Pie Chart */}
      <ResponsiveContainer width="100%" height={320}>
        <PieChart margin={{ top: 20, right: 0, bottom: 0, left: 0 }}>
          <Pie
            data={chartData}
            cx="50%"
            cy="42%"
            labelLine={false}
            label={renderCustomizedLabel}
            outerRadius={85}
            innerRadius={32}
            fill="#8884d8"
            dataKey="value_cad"
            nameKey="name"
            paddingAngle={2}
          >
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={ACCOUNT_COLORS[entry.code] || `hsl(${index * 137.5}, 70%, 50%)`}
                stroke="white"
                strokeWidth={2}
              />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
          <Legend content={<CustomLegend />} />
        </PieChart>
      </ResponsiveContainer>

      {/* Account Details Table */}
      <div className="mt-4 border-t border-secondary-100 pt-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-secondary-500 text-left">
              <th className="pb-2 font-medium">Account</th>
              <th className="pb-2 font-medium text-right">Value</th>
              <th className="pb-2 font-medium text-right">Return</th>
              <th className="pb-2 font-medium text-right hidden sm:table-cell">Holdings</th>
            </tr>
          </thead>
          <tbody className="text-secondary-900">
            {chartData.map((account) => (
              <tr key={account.code} className="border-t border-secondary-50">
                <td className="py-2">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: ACCOUNT_COLORS[account.code] }}
                    />
                    <span className="font-medium">{account.name}</span>
                    {account.code !== 'UNASSIGNED' && (
                      <TaxBadge isTaxAdvantaged={account.is_tax_advantaged} />
                    )}
                  </div>
                </td>
                <td className="py-2 text-right font-medium">
                  {formatCurrency(account.value_cad, 'CAD')}
                </td>
                <td className={`py-2 text-right ${account.gain_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {account.gain_pct >= 0 ? '+' : ''}{account.gain_pct.toFixed(1)}%
                </td>
                <td className="py-2 text-right text-secondary-500 hidden sm:table-cell">
                  {account.holdings_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
