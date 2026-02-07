import { useState, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import Modal from '../common/Modal';
import { importAPI } from '../../services/api';

const UploadIcon = () => (
  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
  </svg>
);

const CheckIcon = () => (
  <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
);

const WarningIcon = () => (
  <svg className="w-5 h-5 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
  </svg>
);

const platforms = [
  { value: 'td_direct', label: 'TD Direct Investing', description: 'Canada - Activity CSV export' },
  { value: 'wealthsimple', label: 'Wealthsimple', description: 'Canada - Monthly statement CSV' },
];

const accountTypes = [
  { value: '', label: 'Select account type (optional)' },
  { value: 'TFSA', label: 'TFSA - Tax-Free Savings Account' },
  { value: 'RRSP', label: 'RRSP - Registered Retirement Savings Plan' },
  { value: 'FHSA', label: 'FHSA - First Home Savings Account' },
  { value: 'RESP', label: 'RESP - Registered Education Savings Plan' },
  { value: 'LIRA', label: 'LIRA - Locked-In Retirement Account' },
  { value: 'RRIF', label: 'RRIF - Registered Retirement Income Fund' },
  { value: 'NON_REG', label: 'Non-Registered (Taxable)' },
  { value: 'MARGIN', label: 'Margin Account' },
];

export default function ImportModal({ isOpen, onClose }) {
  const queryClient = useQueryClient();

  const [step, setStep] = useState(1); // 1: Upload, 2: Preview, 3: Result
  const [selectedPlatform, setSelectedPlatform] = useState('td_direct');
  const [accountType, setAccountType] = useState('');
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [previewData, setPreviewData] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [error, setError] = useState(null);

  // Preview mutation (handles multiple files by aggregating)
  const previewMutation = useMutation({
    mutationFn: async ({ files, platform, accountType }) => {
      // Preview all files and aggregate results
      const results = await Promise.all(
        files.map(file => importAPI.uploadPreview(file, platform, accountType || null).then(r => r.data))
      );

      // Aggregate results
      const aggregated = {
        platform: platform,
        total_transactions: 0,
        buy_transactions: 0,
        sell_transactions: 0,
        transactions: [],
        new_symbols: new Set(),
        existing_symbols: new Set(),
        potential_duplicates: 0,
        warnings: [],
      };

      results.forEach(result => {
        aggregated.total_transactions += result.total_transactions;
        aggregated.buy_transactions += result.buy_transactions;
        aggregated.sell_transactions += result.sell_transactions;
        aggregated.transactions.push(...result.transactions);
        result.new_symbols.forEach(s => aggregated.new_symbols.add(s));
        result.existing_symbols.forEach(s => aggregated.existing_symbols.add(s));
        aggregated.potential_duplicates += result.potential_duplicates;
        aggregated.warnings.push(...result.warnings);
      });

      return {
        ...aggregated,
        new_symbols: Array.from(aggregated.new_symbols),
        existing_symbols: Array.from(aggregated.existing_symbols),
      };
    },
    onSuccess: (data) => {
      setPreviewData(data);
      setStep(2);
      setError(null);
    },
    onError: (err) => {
      setError(err.response?.data?.detail || 'Failed to preview file');
    },
  });

  // Import mutation (single file)
  const importMutation = useMutation({
    mutationFn: async ({ file, platform, accountType, skipDuplicates }) => {
      const response = await importAPI.uploadImport(file, platform, accountType || null, skipDuplicates);
      return response.data;
    },
    onSuccess: (data) => {
      setImportResult(data);
      setStep(3);
      setError(null);
      // Invalidate queries to refresh data
      queryClient.invalidateQueries({ queryKey: ['holdings'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['portfolioSummary'] });
    },
    onError: (err) => {
      setError(err.response?.data?.detail || 'Failed to import transactions');
    },
  });

  // Bulk import mutation (multiple files)
  const bulkImportMutation = useMutation({
    mutationFn: async ({ files, platform, accountType, skipDuplicates }) => {
      const response = await importAPI.uploadBulkImport(files, platform, accountType || null, skipDuplicates);
      return response.data;
    },
    onSuccess: (data) => {
      setImportResult(data);
      setStep(3);
      setError(null);
      // Invalidate queries to refresh data
      queryClient.invalidateQueries({ queryKey: ['holdings'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['portfolioSummary'] });
    },
    onError: (err) => {
      setError(err.response?.data?.detail || 'Failed to import transactions');
    },
  });

  const handleFileChange = useCallback((e) => {
    const files = Array.from(e.target.files || []);
    setSelectedFiles(files);
    setError(null);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    const csvFiles = files.filter(f => f.name.endsWith('.csv'));
    if (csvFiles.length > 0) {
      setSelectedFiles(csvFiles);
      setError(null);
    } else {
      setError('Please drop CSV files only');
    }
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
  }, []);

  const handlePreview = () => {
    if (selectedFiles.length === 0) {
      setError('Please select a file first');
      return;
    }

    // Preview all selected files
    previewMutation.mutate({
      files: selectedFiles,
      platform: selectedPlatform,
      accountType,
    });
  };

  const handleImport = () => {
    if (selectedFiles.length === 0) return;

    if (selectedFiles.length === 1) {
      // Single file import
      importMutation.mutate({
        file: selectedFiles[0],
        platform: selectedPlatform,
        accountType,
        skipDuplicates,
      });
    } else {
      // Bulk import for multiple files
      bulkImportMutation.mutate({
        files: selectedFiles,
        platform: selectedPlatform,
        accountType,
        skipDuplicates,
      });
    }
  };

  const handleClose = () => {
    // Reset state
    setStep(1);
    setSelectedFiles([]);
    setPreviewData(null);
    setImportResult(null);
    setError(null);
    onClose();
  };

  const handleBack = () => {
    setStep(1);
    setPreviewData(null);
    setError(null);
  };

  const renderUploadStep = () => (
    <div className="space-y-6">
      {/* Platform Selection */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Import Source
        </label>
        <div className="grid grid-cols-1 gap-3">
          {platforms.map((platform) => (
            <label
              key={platform.value}
              className={`
                flex items-center p-4 border rounded-lg cursor-pointer transition-colors
                ${selectedPlatform === platform.value
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
                }
              `}
            >
              <input
                type="radio"
                name="platform"
                value={platform.value}
                checked={selectedPlatform === platform.value}
                onChange={(e) => setSelectedPlatform(e.target.value)}
                className="sr-only"
              />
              <div className="flex-1">
                <div className="font-medium text-gray-900">{platform.label}</div>
                <div className="text-sm text-gray-500">{platform.description}</div>
              </div>
              {selectedPlatform === platform.value && <CheckIcon />}
            </label>
          ))}
        </div>
      </div>

      {/* Account Type */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Account Type
        </label>
        <select
          value={accountType}
          onChange={(e) => setAccountType(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          {accountTypes.map((type) => (
            <option key={type.value} value={type.value}>
              {type.label}
            </option>
          ))}
        </select>
      </div>

      {/* File Upload */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          CSV File(s)
        </label>
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          className={`
            relative border-2 border-dashed rounded-lg p-8 text-center transition-colors
            ${selectedFiles.length > 0 ? 'border-green-300 bg-green-50' : 'border-gray-300 hover:border-gray-400'}
          `}
        >
          <input
            type="file"
            accept=".csv"
            multiple
            onChange={handleFileChange}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
          <div className="space-y-2">
            <div className="mx-auto w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center">
              <UploadIcon />
            </div>
            {selectedFiles.length > 0 ? (
              <div>
                <p className="text-sm font-medium text-green-600">
                  {selectedFiles.length} file(s) selected
                </p>
                <ul className="text-sm text-gray-500 mt-2">
                  {selectedFiles.map((file, i) => (
                    <li key={i}>{file.name}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <div>
                <p className="text-sm font-medium text-gray-700">
                  Drop CSV files here or click to browse
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Only CSV files are supported
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Skip Duplicates Option */}
      <label className="flex items-center gap-3">
        <input
          type="checkbox"
          checked={skipDuplicates}
          onChange={(e) => setSkipDuplicates(e.target.checked)}
          className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
        />
        <span className="text-sm text-gray-700">
          Skip duplicate transactions (recommended)
        </span>
      </label>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error}
        </div>
      )}
    </div>
  );

  const renderPreviewStep = () => (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="text-2xl font-bold text-gray-900">{previewData?.total_transactions || 0}</div>
          <div className="text-sm text-gray-500">Total Transactions</div>
        </div>
        <div className="bg-green-50 rounded-lg p-4">
          <div className="text-2xl font-bold text-green-600">{previewData?.buy_transactions || 0}</div>
          <div className="text-sm text-gray-500">Buys</div>
        </div>
        <div className="bg-red-50 rounded-lg p-4">
          <div className="text-2xl font-bold text-red-600">{previewData?.sell_transactions || 0}</div>
          <div className="text-sm text-gray-500">Sells</div>
        </div>
        <div className="bg-yellow-50 rounded-lg p-4">
          <div className="text-2xl font-bold text-yellow-600">{previewData?.potential_duplicates || 0}</div>
          <div className="text-sm text-gray-500">Duplicates</div>
        </div>
      </div>

      {/* Symbols Info */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {previewData?.new_symbols?.length > 0 && (
          <div className="border border-green-200 bg-green-50 rounded-lg p-4">
            <h4 className="font-medium text-green-800 mb-2">New Symbols ({previewData.new_symbols.length})</h4>
            <div className="flex flex-wrap gap-2">
              {previewData.new_symbols.map((symbol) => (
                <span key={symbol} className="px-2 py-1 bg-green-200 text-green-800 text-sm rounded">
                  {symbol}
                </span>
              ))}
            </div>
          </div>
        )}
        {previewData?.existing_symbols?.length > 0 && (
          <div className="border border-blue-200 bg-blue-50 rounded-lg p-4">
            <h4 className="font-medium text-blue-800 mb-2">Existing Symbols ({previewData.existing_symbols.length})</h4>
            <div className="flex flex-wrap gap-2">
              {previewData.existing_symbols.map((symbol) => (
                <span key={symbol} className="px-2 py-1 bg-blue-200 text-blue-800 text-sm rounded">
                  {symbol}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Warnings */}
      {previewData?.warnings?.length > 0 && (
        <div className="border border-yellow-200 bg-yellow-50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <WarningIcon />
            <h4 className="font-medium text-yellow-800">Warnings ({previewData.warnings.length})</h4>
          </div>
          <ul className="text-sm text-yellow-700 space-y-1 max-h-32 overflow-y-auto">
            {previewData.warnings.map((warning, i) => (
              <li key={i}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Transaction Preview Table */}
      <div>
        <h4 className="font-medium text-gray-900 mb-2">Transaction Preview</h4>
        <div className="border rounded-lg overflow-hidden max-h-64 overflow-y-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50 sticky top-0">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Qty</th>
                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Price</th>
                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Total</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {previewData?.transactions?.slice(0, 50).map((t, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-2 text-sm text-gray-900">{t.date}</td>
                  <td className="px-4 py-2 text-sm font-medium text-gray-900">{t.symbol}</td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-0.5 text-xs rounded-full ${
                      t.transaction_type === 'BUY'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {t.transaction_type}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-sm text-right text-gray-900">{parseFloat(t.quantity).toFixed(2)}</td>
                  <td className="px-4 py-2 text-sm text-right text-gray-900">${parseFloat(t.price_per_share).toFixed(2)}</td>
                  <td className="px-4 py-2 text-sm text-right font-medium text-gray-900">
                    ${(parseFloat(t.quantity) * parseFloat(t.price_per_share)).toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {previewData?.transactions?.length > 50 && (
            <div className="px-4 py-2 bg-gray-50 text-sm text-gray-500 text-center">
              Showing 50 of {previewData.transactions.length} transactions
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error}
        </div>
      )}
    </div>
  );

  const renderResultStep = () => (
    <div className="space-y-6 text-center">
      <div className={`mx-auto w-16 h-16 rounded-full flex items-center justify-center ${
        importResult?.success ? 'bg-green-100' : 'bg-red-100'
      }`}>
        {importResult?.success ? (
          <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        ) : (
          <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        )}
      </div>

      <div>
        <h3 className="text-xl font-semibold text-gray-900">
          {importResult?.success ? 'Import Successful!' : 'Import Failed'}
        </h3>
        <p className="text-gray-500 mt-1">
          {importResult?.success
            ? 'Your transactions have been imported successfully.'
            : 'There was an error importing your transactions.'}
        </p>
      </div>

      {importResult?.success && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-green-50 rounded-lg p-4">
            <div className="text-2xl font-bold text-green-600">{importResult.transactions_imported}</div>
            <div className="text-sm text-gray-500">Imported</div>
          </div>
          <div className="bg-blue-50 rounded-lg p-4">
            <div className="text-2xl font-bold text-blue-600">{importResult.holdings_created}</div>
            <div className="text-sm text-gray-500">Holdings Created</div>
          </div>
          <div className="bg-purple-50 rounded-lg p-4">
            <div className="text-2xl font-bold text-purple-600">{importResult.holdings_updated}</div>
            <div className="text-sm text-gray-500">Holdings Updated</div>
          </div>
          <div className="bg-yellow-50 rounded-lg p-4">
            <div className="text-2xl font-bold text-yellow-600">{importResult.duplicates_skipped}</div>
            <div className="text-sm text-gray-500">Duplicates Skipped</div>
          </div>
        </div>
      )}

      {importResult?.errors?.length > 0 && (
        <div className="border border-red-200 bg-red-50 rounded-lg p-4 text-left">
          <h4 className="font-medium text-red-800 mb-2">Errors</h4>
          <ul className="text-sm text-red-700 space-y-1">
            {importResult.errors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {importResult?.warnings?.length > 0 && (
        <div className="border border-yellow-200 bg-yellow-50 rounded-lg p-4 text-left">
          <h4 className="font-medium text-yellow-800 mb-2">Warnings</h4>
          <ul className="text-sm text-yellow-700 space-y-1 max-h-32 overflow-y-auto">
            {importResult.warnings.map((warning, i) => (
              <li key={i}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );

  const renderFooter = () => {
    if (step === 1) {
      return (
        <>
          <button
            onClick={handleClose}
            className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handlePreview}
            disabled={selectedFiles.length === 0 || previewMutation.isPending}
            className="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {previewMutation.isPending ? 'Loading...' : 'Preview'}
          </button>
        </>
      );
    }

    if (step === 2) {
      const isImporting = importMutation.isPending || bulkImportMutation.isPending;
      return (
        <>
          <button
            onClick={handleBack}
            disabled={isImporting}
            className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
          >
            Back
          </button>
          <button
            onClick={handleImport}
            disabled={isImporting || (previewData?.total_transactions || 0) === 0}
            className="px-4 py-2 text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isImporting ? 'Importing...' : `Import ${previewData?.total_transactions || 0} Transactions`}
          </button>
        </>
      );
    }

    return (
      <button
        onClick={handleClose}
        className="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
      >
        Done
      </button>
    );
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={step === 1 ? 'Import Transactions' : step === 2 ? 'Review Import' : 'Import Complete'}
      subtitle={
        step === 1
          ? 'Import transactions from your broker CSV exports'
          : step === 2
          ? 'Review the transactions before importing'
          : null
      }
      size="2xl"
      footer={renderFooter()}
    >
      {step === 1 && renderUploadStep()}
      {step === 2 && renderPreviewStep()}
      {step === 3 && renderResultStep()}
    </Modal>
  );
}
