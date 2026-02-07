import { useState, useEffect } from 'react';
import { useUpdateHolding, useAccountTypes } from '../../hooks/useHoldings';
import Modal from '../common/Modal';
import Input from '../common/Input';
import Button from '../common/Button';

export default function EditHoldingModal({ holding, isOpen, onClose }) {
  const updateHolding = useUpdateHolding();
  const { data: accountTypesData } = useAccountTypes();
  const accountTypes = accountTypesData?.account_types || [];

  const [formData, setFormData] = useState({
    company_name: '',
    quantity: '',
    avg_purchase_price: '',
    account_type: '',
    first_purchase_date: '',
    notes: '',
  });

  useEffect(() => {
    if (holding) {
      setFormData({
        company_name: holding.company_name || '',
        quantity: holding.quantity || '',
        avg_purchase_price: holding.avg_purchase_price || '',
        account_type: holding.account_type || '',
        first_purchase_date: holding.first_purchase_date || '',
        notes: holding.notes || '',
      });
    }
  }, [holding]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      await updateHolding.mutateAsync({ id: holding.id, data: formData });
      onClose();
    } catch (error) {
      console.error('Error updating holding:', error);
    }
  };

  if (!holding) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Edit ${holding.symbol}`}>
      <form onSubmit={handleSubmit}>
        <Input
          label="Company Name"
          name="company_name"
          value={formData.company_name}
          onChange={handleChange}
        />

        <Input
          label="Quantity *"
          name="quantity"
          type="number"
          step="0.0001"
          value={formData.quantity}
          onChange={handleChange}
          required
        />

        <Input
          label="Average Purchase Price *"
          name="avg_purchase_price"
          type="number"
          step="0.01"
          value={formData.avg_purchase_price}
          onChange={handleChange}
          required
        />

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Account Type
          </label>
          <select
            name="account_type"
            value={formData.account_type}
            onChange={handleChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">-- Select Account --</option>
            {accountTypes.map((type) => (
              <option key={type.code} value={type.code}>
                {type.name}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-500 mt-1">
            Assign to TFSA, RRSP, FHSA, or Non-Registered account
          </p>
        </div>

        <Input
          label="First Purchase Date"
          name="first_purchase_date"
          type="date"
          value={formData.first_purchase_date}
          onChange={handleChange}
        />

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Notes
          </label>
          <textarea
            name="notes"
            value={formData.notes}
            onChange={handleChange}
            rows="3"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={updateHolding.isPending}>
            {updateHolding.isPending ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>

        {updateHolding.isError && (
          <p className="mt-2 text-sm text-red-600">
            {updateHolding.error?.response?.data?.detail || 'Failed to update holding'}
          </p>
        )}
      </form>
    </Modal>
  );
}
