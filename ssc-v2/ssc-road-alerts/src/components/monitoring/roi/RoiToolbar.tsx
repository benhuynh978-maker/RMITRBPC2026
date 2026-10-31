export interface RoiToolbarProps {
  count: number;
  hasSelection: boolean;
  hasSaved: boolean;
  disabled: boolean;
  onUndo: () => void;
  onDeleteSelected: () => void;
  onClear: () => void;
  onLoadSaved: () => void;
}

export function RoiToolbar({ count, hasSelection, hasSaved, disabled, onUndo, onDeleteSelected, onClear, onLoadSaved }: RoiToolbarProps) {
  return <div className="roi-toolbar" role="group" aria-label="Zone editing tools">
    <button type="button" className="secondary" disabled={disabled || count === 0} onClick={onUndo}>Undo last point</button>
    <button type="button" className="secondary" disabled={disabled || !hasSelection} onClick={onDeleteSelected}>Delete selected point</button>
    <button type="button" className="secondary" disabled={disabled || count === 0} onClick={onClear}>Clear all</button>
    <button type="button" className="secondary" disabled={disabled || !hasSaved} onClick={onLoadSaved}>Start from saved ROI</button>
  </div>;
}
