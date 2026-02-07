import { useState } from 'react';

const REGIONS = [
  { id: 'all', label: 'All', flag: '🌐' },
  { id: 'CA', label: 'Canada', flag: '🇨🇦' },
  { id: 'IN', label: 'India', flag: '🇮🇳' },
];

export default function RegionFilter({ value, onChange }) {
  return (
    <div className="inline-flex rounded-lg border border-secondary-200 bg-white p-1 shadow-sm">
      {REGIONS.map((region) => (
        <button
          key={region.id}
          onClick={() => onChange(region.id)}
          className={`
            px-3 py-1.5 text-sm font-medium rounded-md transition-all duration-200
            ${value === region.id
              ? 'bg-primary-600 text-white shadow-sm'
              : 'text-secondary-600 hover:bg-secondary-50'
            }
          `}
        >
          <span className="mr-1.5">{region.flag}</span>
          {region.label}
        </button>
      ))}
    </div>
  );
}
