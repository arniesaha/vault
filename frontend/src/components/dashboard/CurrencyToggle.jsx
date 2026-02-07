import { useState, useRef, useEffect } from 'react';

const CURRENCIES = [
  { code: 'CAD', symbol: 'CA$', flag: '🇨🇦', name: 'Canadian Dollar' },
  { code: 'USD', symbol: 'US$', flag: '🇺🇸', name: 'US Dollar' },
  { code: 'INR', symbol: '₹', flag: '🇮🇳', name: 'Indian Rupee' },
];

// Fallback rates FROM CAD (used if API fails)
const FALLBACK_RATES = {
  CAD: 1.0,
  USD: 0.73,
  INR: 62.5,
};

export function convertFromCAD(amountCAD, toCurrency, rates = FALLBACK_RATES) {
  if (!amountCAD || !toCurrency) return amountCAD;
  const rate = rates[toCurrency] ?? FALLBACK_RATES[toCurrency] ?? 1;
  return amountCAD * rate;
}

export function formatCurrencyWithConversion(amountCAD, displayCurrency, rates = FALLBACK_RATES) {
  if (amountCAD === null || amountCAD === undefined) return '—';
  
  const converted = convertFromCAD(amountCAD, displayCurrency, rates);
  
  // Format based on currency
  const formatter = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: displayCurrency,
    minimumFractionDigits: displayCurrency === 'INR' ? 0 : 2,
    maximumFractionDigits: displayCurrency === 'INR' ? 0 : 2,
  });
  
  return formatter.format(converted);
}

export default function CurrencyToggle({ value, onChange, rates }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);
  
  const selected = CURRENCIES.find(c => c.code === value) || CURRENCIES[0];
  
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  
  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 bg-white border border-secondary-200 rounded-lg text-sm font-medium text-secondary-700 hover:bg-secondary-50 transition-colors"
        title={rates ? 'Live exchange rates' : 'Using fallback rates'}
      >
        <span>{selected.flag}</span>
        <span>{selected.code}</span>
        {rates && (
          <span className="w-1.5 h-1.5 bg-green-500 rounded-full" title="Live rates" />
        )}
        <svg 
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      
      {isOpen && (
        <div className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg border border-secondary-200 py-1 z-50">
          {CURRENCIES.map((currency) => {
            const rate = rates?.[currency.code] ?? FALLBACK_RATES[currency.code];
            return (
              <button
                key={currency.code}
                onClick={() => {
                  onChange(currency.code);
                  setIsOpen(false);
                }}
                className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left hover:bg-secondary-50 transition-colors ${
                  currency.code === value ? 'bg-primary-50 text-primary-700' : 'text-secondary-700'
                }`}
              >
                <span className="text-lg">{currency.flag}</span>
                <div className="flex-1">
                  <div className="font-medium">{currency.code}</div>
                  <div className="text-xs text-secondary-500">{currency.name}</div>
                </div>
                {currency.code !== 'CAD' && (
                  <span className="text-xs text-secondary-400">
                    1 CAD = {rate?.toFixed(currency.code === 'INR' ? 2 : 4)}
                  </span>
                )}
                {currency.code === value && (
                  <svg className="w-4 h-4 text-primary-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            );
          })}
          {rates && (
            <div className="px-4 py-2 text-xs text-secondary-400 border-t border-secondary-100">
              ✓ Live rates
            </div>
          )}
        </div>
      )}
    </div>
  );
}
