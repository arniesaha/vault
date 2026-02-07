import { formatCurrency, formatDate, formatNumber } from '../../utils/formatters';
import Button, { IconButton } from '../common/Button';
import { EmptyState } from '../common/Card';

// Icons
const EditIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
  </svg>
);

const TrashIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
  </svg>
);

const FolderIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
  </svg>
);

// Country badge colors
const COUNTRY_STYLES = {
  CA: 'bg-red-100 text-red-700',
  US: 'bg-blue-100 text-blue-700',
  IN: 'bg-orange-100 text-orange-700',
};

// Exchange badge colors
const EXCHANGE_STYLES = {
  TSX: 'bg-red-50 text-red-600 ring-red-500/20',
  'TSX-V': 'bg-red-50 text-red-500 ring-red-500/20',
  NASDAQ: 'bg-blue-50 text-blue-600 ring-blue-500/20',
  NYSE: 'bg-blue-50 text-blue-500 ring-blue-500/20',
  NSE: 'bg-orange-50 text-orange-600 ring-orange-500/20',
  BSE: 'bg-orange-50 text-orange-500 ring-orange-500/20',
};

// Account type badge colors
const ACCOUNT_STYLES = {
  TFSA: 'bg-green-100 text-green-700',
  RRSP: 'bg-blue-100 text-blue-700',
  FHSA: 'bg-purple-100 text-purple-700',
  RESP: 'bg-amber-100 text-amber-700',
  LIRA: 'bg-indigo-100 text-indigo-700',
  RRIF: 'bg-sky-100 text-sky-700',
  NON_REG: 'bg-red-100 text-red-700',
  MARGIN: 'bg-orange-100 text-orange-700',
  DEMAT: 'bg-teal-100 text-teal-700',
  MF_INDIA: 'bg-violet-100 text-violet-700',
  NRO: 'bg-pink-100 text-pink-700',
  NRE: 'bg-rose-100 text-rose-700',
};

const ACCOUNT_NAMES = {
  TFSA: 'TFSA',
  RRSP: 'RRSP',
  FHSA: 'FHSA',
  RESP: 'RESP',
  LIRA: 'LIRA',
  RRIF: 'RRIF',
  NON_REG: 'Non-Reg',
  MARGIN: 'Margin',
  DEMAT: 'DEMAT',
  MF_INDIA: 'MF India',
  NRO: 'NRO',
  NRE: 'NRE',
};

export default function HoldingsTable({ holdings, onEdit, onDelete }) {
  if (!holdings || holdings.length === 0) {
    return (
      <EmptyState
        icon={FolderIcon}
        title="No holdings yet"
        description="Add your first holding to start tracking your portfolio performance."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full">
        <thead>
          <tr className="bg-secondary-50 border-b border-secondary-200">
            <th className="px-6 py-4 text-left text-xs font-semibold text-secondary-600 uppercase tracking-wider">
              Stock
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold text-secondary-600 uppercase tracking-wider">
              Account
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold text-secondary-600 uppercase tracking-wider">
              Exchange
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold text-secondary-600 uppercase tracking-wider hidden lg:table-cell">
              Country
            </th>
            <th className="px-6 py-4 text-right text-xs font-semibold text-secondary-600 uppercase tracking-wider">
              Quantity
            </th>
            <th className="px-6 py-4 text-right text-xs font-semibold text-secondary-600 uppercase tracking-wider">
              Avg Cost
            </th>
            <th className="px-6 py-4 text-left text-xs font-semibold text-secondary-600 uppercase tracking-wider hidden md:table-cell">
              First Purchase
            </th>
            <th className="px-6 py-4 text-right text-xs font-semibold text-secondary-600 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-secondary-100">
          {holdings.map((holding, index) => (
            <tr
              key={holding.id}
              className={`hover:bg-secondary-50 transition-colors ${index % 2 === 1 ? 'bg-secondary-50/50' : ''}`}
            >
              <td className="px-6 py-4 whitespace-nowrap">
                <div>
                  <div className="text-sm font-semibold text-secondary-900">{holding.symbol}</div>
                  <div className="text-xs text-secondary-500 truncate max-w-[200px]">
                    {holding.company_name || '-'}
                  </div>
                </div>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                {holding.account_type ? (
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${ACCOUNT_STYLES[holding.account_type] || 'bg-secondary-100 text-secondary-700'}`}>
                    {ACCOUNT_NAMES[holding.account_type] || holding.account_type}
                  </span>
                ) : (
                  <span className="text-xs text-secondary-400 italic">Not set</span>
                )}
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ring-1 ring-inset ${EXCHANGE_STYLES[holding.exchange] || 'bg-secondary-50 text-secondary-600 ring-secondary-500/20'}`}>
                  {holding.exchange}
                </span>
              </td>
              <td className="px-6 py-4 whitespace-nowrap hidden lg:table-cell">
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${COUNTRY_STYLES[holding.country] || 'bg-secondary-100 text-secondary-700'}`}>
                  {holding.country}
                </span>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-secondary-900 tabular-nums font-medium">
                {formatNumber(holding.quantity, 4)}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-secondary-900 tabular-nums">
                {formatCurrency(holding.avg_purchase_price, holding.currency)}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-secondary-500 hidden md:table-cell">
                {formatDate(holding.first_purchase_date)}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-right">
                <div className="flex items-center justify-end gap-1">
                  <IconButton
                    icon={EditIcon}
                    onClick={() => onEdit(holding)}
                    title="Edit holding"
                    variant="ghost"
                    size="sm"
                  />
                  <IconButton
                    icon={TrashIcon}
                    onClick={() => onDelete(holding.id)}
                    title="Delete holding"
                    variant="danger"
                    size="sm"
                  />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
