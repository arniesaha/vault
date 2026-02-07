import { useState } from 'react';
import { useHoldings, useDeleteHolding, useAccountTypes } from '../hooks/useHoldings';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import LoadingSpinner, { SkeletonTable } from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';
import HoldingsTable from '../components/holdings/HoldingsTable';
import AddHoldingForm from '../components/holdings/AddHoldingForm';
import EditHoldingModal from '../components/holdings/EditHoldingModal';
import Modal, { ConfirmModal } from '../components/common/Modal';

// Icons
const PlusIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
  </svg>
);

const HoldingsIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
  </svg>
);

const FilterIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
  </svg>
);

export default function Holdings() {
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingHolding, setEditingHolding] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [accountTypeFilter, setAccountTypeFilter] = useState('');

  const filters = accountTypeFilter ? { account_type: accountTypeFilter } : {};
  const { data: holdings, isLoading, isError, error, refetch } = useHoldings(filters);
  const { data: accountTypesData } = useAccountTypes();
  const deleteHolding = useDeleteHolding();

  const accountTypes = accountTypesData?.account_types || [];

  const handleDelete = async () => {
    if (!deletingId) return;
    try {
      await deleteHolding.mutateAsync(deletingId);
      setDeletingId(null);
    } catch (error) {
      console.error('Error deleting holding:', error);
    }
  };

  return (
    <div className="container-app py-6 sm:py-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-secondary-900">Holdings</h1>
          <p className="text-secondary-500 mt-1">Manage your investment portfolio</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {/* Account Type Filter */}
          <div className="flex items-center gap-2">
            <FilterIcon className="w-4 h-4 text-secondary-400" />
            <select
              value={accountTypeFilter}
              onChange={(e) => setAccountTypeFilter(e.target.value)}
              className="text-sm border border-secondary-200 rounded-lg px-3 py-2 bg-white text-secondary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            >
              <option value="">All Accounts</option>
              {accountTypes.map((type) => (
                <option key={type.code} value={type.code}>
                  {type.name}
                </option>
              ))}
              <option value="UNASSIGNED">Unassigned</option>
            </select>
          </div>
          <Button icon={PlusIcon} onClick={() => setShowAddForm(true)}>
            Add Holding
          </Button>
        </div>
      </div>

      {/* Holdings Card */}
      <div className="bg-white rounded-xl shadow-soft border border-secondary-100 overflow-hidden">
        {isLoading && (
          <SkeletonTable rows={5} />
        )}

        {isError && (
          <div className="p-6">
            <ErrorMessage
              title="Failed to load holdings"
              message={error?.response?.data?.detail || 'Could not connect to the server. Please check if the backend is running.'}
              onRetry={() => refetch()}
            />
          </div>
        )}

        {!isLoading && !isError && (
          <HoldingsTable
            holdings={holdings}
            onEdit={setEditingHolding}
            onDelete={setDeletingId}
          />
        )}
      </div>

      {/* Add Holding Modal */}
      <Modal
        isOpen={showAddForm}
        onClose={() => setShowAddForm(false)}
        title="Add New Holding"
        subtitle="Add a stock to your portfolio"
        icon={HoldingsIcon}
        size="lg"
      >
        <AddHoldingForm
          onSuccess={() => setShowAddForm(false)}
          onCancel={() => setShowAddForm(false)}
        />
      </Modal>

      {/* Edit Holding Modal */}
      <EditHoldingModal
        holding={editingHolding}
        isOpen={!!editingHolding}
        onClose={() => setEditingHolding(null)}
      />

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={!!deletingId}
        onClose={() => setDeletingId(null)}
        onConfirm={handleDelete}
        title="Delete Holding"
        message="Are you sure you want to delete this holding? This action cannot be undone."
        confirmText="Delete"
        cancelText="Cancel"
        variant="danger"
        loading={deleteHolding.isPending}
      />
    </div>
  );
}
