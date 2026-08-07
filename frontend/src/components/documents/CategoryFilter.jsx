/**
 * CategoryFilter.jsx
 * ─────────────────────────────────────────────────────────────
 * Horizontal pill/badge filter for document categories.
 * Shows count per category and highlights the active selection.
 * ─────────────────────────────────────────────────────────────
 */

import { motion } from 'framer-motion'
import { CATEGORIES } from '../../services/documentService'

const ALL_CATEGORIES = ['All', ...CATEGORIES]

// Colour accent per category
const CATEGORY_COLORS = {
  All:       'bg-surface-800 text-white',
  HR:        'bg-violet-500 text-white',
  Finance:   'bg-emerald-500 text-white',
  Legal:     'bg-amber-500 text-white',
  IT:        'bg-cyan-500 text-white',
  Policies:  'bg-orange-500 text-white',
  Research:  'bg-indigo-500 text-white',
  General:   'bg-slate-500 text-white',
}

const CATEGORY_COLORS_INACTIVE = {
  All:       'text-surface-600 hover:bg-surface-100',
  HR:        'text-violet-600 hover:bg-violet-50',
  Finance:   'text-emerald-600 hover:bg-emerald-50',
  Legal:     'text-amber-600 hover:bg-amber-50',
  IT:        'text-cyan-600 hover:bg-cyan-50',
  Policies:  'text-orange-600 hover:bg-orange-50',
  Research:  'text-indigo-600 hover:bg-indigo-50',
  General:   'text-slate-600 hover:bg-slate-50',
}

/**
 * @param {string}   activeCategory - Currently selected category
 * @param {Function} onChange       - Called with new category string
 * @param {Array}    documents      - All documents (for count badges)
 */
export function CategoryFilter({ activeCategory, onChange, documents = [] }) {
  // Count per category
  const counts = ALL_CATEGORIES.reduce((acc, cat) => {
    if (cat === 'All') {
      acc[cat] = documents.length
    } else {
      acc[cat] = documents.filter((d) => d.category === cat).length
    }
    return acc
  }, {})

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {ALL_CATEGORIES.map((cat) => {
        const isActive = activeCategory === cat
        const count = counts[cat]

        return (
          <motion.button
            key={cat}
            whileTap={{ scale: 0.96 }}
            onClick={() => onChange(cat)}
            className={`relative inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-150
              ${isActive
                ? CATEGORY_COLORS[cat]
                : `bg-transparent ${CATEGORY_COLORS_INACTIVE[cat]}`
              }`}
          >
            {cat}
            {count > 0 && (
              <span
                className={`inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold
                  ${isActive ? 'bg-white/20 text-white' : 'bg-surface-200 text-surface-500'}`}
              >
                {count}
              </span>
            )}
          </motion.button>
        )
      })}
    </div>
  )
}
