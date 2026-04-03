import { useEffect, useMemo, useRef, useState } from "react";
import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";

const monthNames = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

const weekDays = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

function usePopover(initialOpen = false) {
  const [open, setOpen] = useState(initialOpen);
  const ref = useRef(null);

  useEffect(() => {
    function handleOutside(event) {
      if (ref.current && !ref.current.contains(event.target)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  return { open, setOpen, ref };
}

function formatDateLabel(value) {
  if (!value) {
    return "Select date";
  }

  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function formatMonthLabel(value) {
  if (!value) {
    return "Select month";
  }

  const [year, month] = value.split("-").map(Number);
  return new Intl.DateTimeFormat("en-IN", {
    month: "long",
    year: "numeric",
  }).format(new Date(year, month - 1, 1));
}

function buildMonthGrid(viewDate, selectedValue) {
  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();
  const firstDay = new Date(year, month, 1);
  const startOffset = firstDay.getDay();
  const startDate = new Date(year, month, 1 - startOffset);

  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(startDate);
    date.setDate(startDate.getDate() + index);
    const value = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    return {
      label: date.getDate(),
      value,
      muted: date.getMonth() !== month,
      selected: value === selectedValue,
    };
  });
}

export function SelectField({
  label,
  value,
  onChange,
  options,
  placeholder = "Select option",
}) {
  const { open, setOpen, ref } = usePopover(false);
  const selected = options.find((option) => String(option.value) === String(value));

  return (
    <div className={`custom-field ${open ? "is-open" : ""}`} ref={ref}>
      <span className="custom-field__label">{label}</span>
      <button className="custom-trigger" type="button" onClick={() => setOpen((state) => !state)}>
        <span>{selected?.label || placeholder}</span>
        <ChevronDown size={16} />
      </button>
      {open && (
        <div className="custom-popover">
          {options.map((option) => (
            <button
              key={`${label}-${option.value}`}
              className={`custom-option ${String(option.value) === String(value) ? "is-selected" : ""}`}
              type="button"
              onClick={() => {
                onChange(option.value);
                setOpen(false);
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function DateField({ label, value, onChange }) {
  const { open, setOpen, ref } = usePopover(false);
  const initialView = value ? new Date(value) : new Date();
  const [viewDate, setViewDate] = useState(new Date(initialView.getFullYear(), initialView.getMonth(), 1));
  const monthGrid = useMemo(() => buildMonthGrid(viewDate, value), [viewDate, value]);

  return (
    <div className={`custom-field ${open ? "is-open" : ""}`} ref={ref}>
      <span className="custom-field__label">{label}</span>
      <button className="custom-trigger" type="button" onClick={() => setOpen((state) => !state)}>
        <span>{formatDateLabel(value)}</span>
        <CalendarDays size={16} />
      </button>
      {open && (
        <div className="custom-popover custom-popover--calendar">
          <div className="calendar-head">
            <button type="button" onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1))}>
              <ChevronLeft size={16} />
            </button>
            <strong>
              {monthNames[viewDate.getMonth()]} {viewDate.getFullYear()}
            </strong>
            <button type="button" onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1))}>
              <ChevronRight size={16} />
            </button>
          </div>
          <div className="calendar-grid calendar-grid--labels">
            {weekDays.map((day) => (
              <span key={day}>{day}</span>
            ))}
          </div>
          <div className="calendar-grid">
            {monthGrid.map((day) => (
              <button
                key={day.value}
                type="button"
                className={`calendar-day ${day.muted ? "is-muted" : ""} ${day.selected ? "is-selected" : ""}`}
                onClick={() => {
                  onChange(day.value);
                  setOpen(false);
                }}
              >
                {day.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function MonthField({ label, value, onChange }) {
  const { open, setOpen, ref } = usePopover(false);
  const [viewYear, setViewYear] = useState(value ? Number(value.split("-")[0]) : new Date().getFullYear());

  return (
    <div className={`custom-field ${open ? "is-open" : ""}`} ref={ref}>
      <span className="custom-field__label">{label}</span>
      <button className="custom-trigger" type="button" onClick={() => setOpen((state) => !state)}>
        <span>{formatMonthLabel(value)}</span>
        <CalendarDays size={16} />
      </button>
      {open && (
        <div className="custom-popover custom-popover--calendar">
          <div className="calendar-head">
            <button type="button" onClick={() => setViewYear((year) => year - 1)}>
              <ChevronLeft size={16} />
            </button>
            <strong>{viewYear}</strong>
            <button type="button" onClick={() => setViewYear((year) => year + 1)}>
              <ChevronRight size={16} />
            </button>
          </div>
          <div className="month-grid">
            {monthNames.map((month, index) => {
              const optionValue = `${viewYear}-${String(index + 1).padStart(2, "0")}`;
              return (
                <button
                  key={optionValue}
                  type="button"
                  className={`month-chip ${optionValue === value ? "is-selected" : ""}`}
                  onClick={() => {
                    onChange(optionValue);
                    setOpen(false);
                  }}
                >
                  {month}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
