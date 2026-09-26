import React, { useState, useRef } from 'react'
import { ChevronDown } from 'lucide-react'
import '../styles/HexColorPicker.css'

const PRESETS = [
  '#6366f1', // Indigo
  '#06b6d4', // Cyan
  '#ec4899', // Pink
  '#f59e0b', // Amber
  '#10b981', // Emerald
  '#8b5cf6', // Violet
  '#ef4444', // Red
  '#3b82f6', // Blue
]

export default function HexColorPicker({ value, onChange }) {
  const [isOpen, setIsOpen] = useState(false)
  const [inputValue, setInputValue] = useState(value)
  const ref = useRef(null)

  const handleColorChange = (e) => {
    const val = e.target.value
    setInputValue(val)
    if (/^#[0-9A-F]{6}$/i.test(val)) {
      onChange(val)
    }
  }

  const handlePresetClick = (color) => {
    setInputValue(color)
    onChange(color)
    setIsOpen(false)
  }

  return (
    <div className="hex-color-picker" ref={ref}>
      <button
        className="color-button glass"
        onClick={() => setIsOpen(!isOpen)}
        style={{ background: `linear-gradient(135deg, ${value}, rgba(99, 102, 241, 0.3))` }}
      >
        <span className="color-label">THEME</span>
        <ChevronDown size={16} style={{ transform: isOpen ? 'rotate(180deg)' : '' }} />
      </button>

      {isOpen && (
        <div className="color-picker-menu glass">
          <div className="color-input-group">
            <label>HEX</label>
            <input
              type="text"
              value={inputValue}
              onChange={handleColorChange}
              placeholder="#6366f1"
              maxLength={7}
            />
          </div>

          <div className="presets-label">PRESETS</div>
          <div className="color-presets">
            {PRESETS.map((color) => (
              <button
                key={color}
                className={`preset-btn ${value === color ? 'active' : ''}`}
                style={{ background: color }}
                onClick={() => handlePresetClick(color)}
                title={color}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
